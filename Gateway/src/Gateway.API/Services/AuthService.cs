using Gateway.API.Data;
using Gateway.API.DTOs.Auth;
using Gateway.API.Entities;
using Microsoft.EntityFrameworkCore;

namespace Gateway.API.Services;

/// <summary>
/// Handles authentication business logic: registration, login, password hashing.
/// </summary>
public class AuthService
{
  private readonly AppDbContext _db;

  public AuthService(AppDbContext db)
  {
    _db = db;
  }

  /// <summary>
  /// Registers a new user. Returns null if email already exists.
  /// </summary>
  public async Task<AuthResponse?> RegisterAsync(RegisterRequest request)
  {
    // Check for duplicate email
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
}
