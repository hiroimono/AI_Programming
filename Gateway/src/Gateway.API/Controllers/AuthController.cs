using Gateway.API.DTOs.Auth;
using Gateway.API.Services;
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
}
