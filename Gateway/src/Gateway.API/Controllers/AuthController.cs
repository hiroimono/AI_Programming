using System.Security.Claims;
using Gateway.API.DTOs.Auth;
using Gateway.API.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace Gateway.API.Controllers;

/// <summary>
/// Authentication endpoints: register, login, refresh, logout.
/// </summary>
[ApiController]
[Route("api/[controller]")]
public class AuthController : ControllerBase
{
  private readonly AuthService _authService;

  public AuthController(AuthService authService)
  {
    _authService = authService;
  }

  /// <summary>
  /// POST /api/auth/register — creates a new user account.
  /// </summary>
  [HttpPost("register")]
  public async Task<IActionResult> Register([FromBody] RegisterRequest request)
  {
    var result = await _authService.RegisterAsync(request);

    if (result is null)
      return Conflict(new { message = "Email already registered" });

    return CreatedAtAction(nameof(Register), new { id = result.Id }, result);
  }

  /// <summary>
  /// POST /api/auth/login — authenticates user and returns JWT token.
  /// </summary>
  [HttpPost("login")]
  public async Task<IActionResult> Login([FromBody] LoginRequest request)
  {
    var result = await _authService.LoginAsync(request);

    if (result is null)
      return Unauthorized(new { message = "Invalid email or password" });

    return Ok(result);
  }

  /// <summary>
  /// POST /api/auth/refresh — issues a new access token using a valid refresh token.
  /// </summary>
  [HttpPost("refresh")]
  public async Task<IActionResult> Refresh([FromBody] RefreshRequest request)
  {
    var result = await _authService.RefreshAsync(request);

    if (result is null)
      return Unauthorized(new { message = "Invalid or expired refresh token" });

    return Ok(result);
  }

  /// <summary>
  /// POST /api/auth/logout — revokes the refresh token.
  /// </summary>
  [HttpPost("logout")]
  public async Task<IActionResult> Logout([FromBody] RefreshRequest request)
  {
    var success = await _authService.LogoutAsync(request);

    if (!success)
      return BadRequest(new { message = "Invalid token" });

    return Ok(new { message = "Logged out successfully" });
  }

  /// <summary>
  /// POST /api/auth/google — authenticates user via Google id_token.
  /// Auto-registers if the user doesn't exist yet.
  /// </summary>
  [HttpPost("google")]
  public async Task<IActionResult> GoogleLogin([FromBody] GoogleLoginRequest request)
  {
    var result = await _authService.GoogleLoginAsync(request);

    if (result is null)
      return Unauthorized(new { message = "Invalid Google token" });

    return Ok(result);
  }

  /// <summary>
  /// GET /api/auth/me — returns current user info from JWT claims. Requires valid token.
  /// </summary>
  [Authorize]
  [HttpGet("me")]
  public IActionResult Me()
  {
    var userId = User.FindFirstValue(ClaimTypes.NameIdentifier)
                 ?? User.FindFirstValue("sub");
    var email = User.FindFirstValue(ClaimTypes.Email)
                ?? User.FindFirstValue("email");
    var firstName = User.FindFirstValue("firstName");
    var lastName = User.FindFirstValue("lastName");
    var roles = User.FindAll("role").Select(c => c.Value).ToList();

    return Ok(new
    {
      id = userId,
      email,
      firstName,
      lastName,
      fullName = $"{firstName} {lastName}",
      roles
    });
  }
}
