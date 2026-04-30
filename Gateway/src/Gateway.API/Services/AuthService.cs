using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using Gateway.API.Data;
using Gateway.API.DTOs.Auth;
using Gateway.API.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;

namespace Gateway.API.Services;

/// <summary>
/// Handles authentication business logic: registration, login, token management.
/// </summary>
public class AuthService
{
  private readonly AppDbContext _db;
  private readonly IConfiguration _config;
  private const int RefreshTokenExpiryDays = 7;

  public AuthService(AppDbContext db, IConfiguration config)
  {
    _db = db;
    _config = config;
  }

  /// <summary>
  /// Registers a new user. Returns null if email already exists.
  /// </summary>
  public async Task<AuthResponse?> RegisterAsync(RegisterRequest request)
  {
    var exists = await _db.Users.AnyAsync(u => u.Email == request.Email.ToLowerInvariant());
    if (exists)
      return null;

    var user = new User
    {
      Id = Guid.NewGuid(),
      Email = request.Email.ToLowerInvariant(),
      PasswordHash = BCrypt.Net.BCrypt.HashPassword(request.Password),
      FirstName = request.FirstName.Trim(),
      LastName = request.LastName.Trim(),
      EmailConfirmed = false,
      CreatedAt = DateTime.UtcNow
    };

    _db.Users.Add(user);
    await _db.SaveChangesAsync();

    return new AuthResponse
    {
      Id = user.Id,
      Email = user.Email,
      FullName = $"{user.FirstName} {user.LastName}",
      Message = "Registration successful"
    };
  }

  /// <summary>
  /// Authenticates a user by email + password. Returns JWT + refresh token on success.
  /// </summary>
  public async Task<AuthResponse?> LoginAsync(LoginRequest request)
  {
    var user = await _db.Users.FirstOrDefaultAsync(u => u.Email == request.Email.ToLowerInvariant());

    // Null PasswordHash means the user registered via external provider (Google/GitHub)
    if (user is null || user.PasswordHash is null || !BCrypt.Net.BCrypt.Verify(request.Password, user.PasswordHash))
      return null;

    user.LastLoginAt = DateTime.UtcNow;

    var (token, expiresAt) = await GenerateJwtTokenAsync(user);
    var refreshToken = await CreateRefreshTokenAsync(user.Id);

    await _db.SaveChangesAsync();

    return new AuthResponse
    {
      Id = user.Id,
      Email = user.Email,
      FullName = $"{user.FirstName} {user.LastName}",
      Token = token,
      RefreshToken = refreshToken.Token,
      ExpiresAt = expiresAt,
      Message = "Login successful"
    };
  }

  /// <summary>
  /// Issues a new access token using a valid refresh token. Implements token rotation.
  /// </summary>
  public async Task<AuthResponse?> RefreshAsync(RefreshRequest request)
  {
    var storedToken = await _db.RefreshTokens
      .Include(rt => rt.User)
      .FirstOrDefaultAsync(rt => rt.Token == request.RefreshToken);

    if (storedToken is null || !storedToken.IsActive)
      return null;

    // Revoke the old refresh token (token rotation — each token is single-use)
    storedToken.RevokedAt = DateTime.UtcNow;

    // Issue new tokens
    var user = storedToken.User;
    var (token, expiresAt) = await GenerateJwtTokenAsync(user);
    var newRefreshToken = await CreateRefreshTokenAsync(user.Id);

    await _db.SaveChangesAsync();

    return new AuthResponse
    {
      Id = user.Id,
      Email = user.Email,
      FullName = $"{user.FirstName} {user.LastName}",
      Token = token,
      RefreshToken = newRefreshToken.Token,
      ExpiresAt = expiresAt,
      Message = "Token refreshed"
    };
  }

  /// <summary>
  /// Revokes a refresh token (logout).
  /// </summary>
  public async Task<bool> LogoutAsync(RefreshRequest request)
  {
    var storedToken = await _db.RefreshTokens
      .FirstOrDefaultAsync(rt => rt.Token == request.RefreshToken);

    if (storedToken is null || !storedToken.IsActive)
      return false;

    storedToken.RevokedAt = DateTime.UtcNow;
    await _db.SaveChangesAsync();
    return true;
  }

  /// <summary>
  /// Creates and persists a new refresh token for the given user.
  /// </summary>
  private async Task<RefreshToken> CreateRefreshTokenAsync(Guid userId)
  {
    var refreshToken = new RefreshToken
    {
      Id = Guid.NewGuid(),
      UserId = userId,
      Token = GenerateSecureToken(),
      CreatedAt = DateTime.UtcNow,
      ExpiresAt = DateTime.UtcNow.AddDays(RefreshTokenExpiryDays)
    };

    _db.RefreshTokens.Add(refreshToken);
    return refreshToken;
  }

  /// <summary>
  /// Generates a cryptographically secure random string for refresh tokens.
  /// </summary>
  private static string GenerateSecureToken()
  {
    var bytes = RandomNumberGenerator.GetBytes(64);
    return Convert.ToBase64String(bytes);
  }

  /// <summary>
  /// Creates a signed JWT containing user claims including organization roles.
  /// </summary>
  private async Task<(string token, DateTime expiresAt)> GenerateJwtTokenAsync(User user)
  {
    var jwtSection = _config.GetSection("Jwt");
    var secret = jwtSection["Secret"]!;
    var issuer = jwtSection["Issuer"]!;
    var audience = jwtSection["Audience"]!;
    var expiryMinutes = int.Parse(jwtSection["ExpiryMinutes"] ?? "60");

    var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(secret));
    var credentials = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);
    var expiresAt = DateTime.UtcNow.AddMinutes(expiryMinutes);

    var claims = new List<Claim>
    {
      new(JwtRegisteredClaimNames.Sub, user.Id.ToString()),
      new(JwtRegisteredClaimNames.Email, user.Email),
      new("firstName", user.FirstName),
      new("lastName", user.LastName),
      new(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString())
    };

    // Add organization roles as claims (e.g., "role": "Owner:org-slug")
    var memberships = await _db.Memberships
      .Include(m => m.Organization)
      .Where(m => m.UserId == user.Id)
      .ToListAsync();

    foreach (var membership in memberships)
    {
      claims.Add(new Claim("role", $"{membership.Role}:{membership.Organization.Slug}"));
    }

    var tokenDescriptor = new JwtSecurityToken(
      issuer: issuer,
      audience: audience,
      claims: claims,
      expires: expiresAt,
      signingCredentials: credentials
    );

    return (new JwtSecurityTokenHandler().WriteToken(tokenDescriptor), expiresAt);
  }

  /// <summary>
  /// Validates a Google id_token and logs in (or auto-registers) the user.
  /// </summary>
  public async Task<AuthResponse?> GoogleLoginAsync(GoogleLoginRequest request)
  {
    // Step 1: Validate the Google id_token using Google's public keys
    var clientId = _config["Google:ClientId"]!;
    Google.Apis.Auth.GoogleJsonWebSignature.Payload payload;

    try
    {
      var settings = new Google.Apis.Auth.GoogleJsonWebSignature.ValidationSettings
      {
        Audience = [clientId] // Only accept tokens issued for OUR app
      };
      payload = await Google.Apis.Auth.GoogleJsonWebSignature.ValidateAsync(request.IdToken, settings);
    }
    catch
    {
      // Token invalid, expired, wrong audience, or tampered with
      return null;
    }

    // Step 2: Extract user info from the verified token
    var email = payload.Email.ToLowerInvariant();
    var firstName = payload.GivenName ?? "User";
    var lastName = payload.FamilyName ?? "";

    // Step 3: Find or create user
    var user = await _db.Users.FirstOrDefaultAsync(u => u.Email == email);

    if (user is null)
    {
      // Auto-register: no password needed (social login)
      user = new User
      {
        Id = Guid.NewGuid(),
        Email = email,
        PasswordHash = null, // No password — Google-only user
        FirstName = firstName,
        LastName = lastName,
        EmailConfirmed = true, // Google already verified the email
        CreatedAt = DateTime.UtcNow
      };
      _db.Users.Add(user);
    }

    // Step 4: Update last login and generate tokens
    user.LastLoginAt = DateTime.UtcNow;

    var (token, expiresAt) = await GenerateJwtTokenAsync(user);
    var refreshToken = await CreateRefreshTokenAsync(user.Id);

    await _db.SaveChangesAsync();

    return new AuthResponse
    {
      Id = user.Id,
      Email = user.Email,
      FullName = $"{user.FirstName} {user.LastName}",
      Token = token,
      RefreshToken = refreshToken.Token,
      ExpiresAt = expiresAt,
      Message = user.CreatedAt == user.LastLoginAt ? "Registration successful via Google" : "Login successful via Google"
    };
  }
}
