using System.ComponentModel.DataAnnotations;

namespace Gateway.API.DTOs.Auth;

/// <summary>
/// Incoming payload for user login.
/// </summary>
public class LoginRequest
{
  [Required, EmailAddress]
  public string Email { get; set; } = string.Empty;

  [Required]
  public string Password { get; set; } = string.Empty;
}
