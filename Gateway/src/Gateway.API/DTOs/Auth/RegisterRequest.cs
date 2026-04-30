using System.ComponentModel.DataAnnotations;

namespace Gateway.API.DTOs.Auth;

/// <summary>
/// Incoming payload for user registration.
/// Validation attributes ensure required fields are present before hitting the service layer.
/// </summary>
public class RegisterRequest
{
  [Required, EmailAddress, MaxLength(256)]
  public string Email { get; set; } = string.Empty;

  [Required, MinLength(8), MaxLength(128)]
  public string Password { get; set; } = string.Empty;

  [Required, MaxLength(100)]
  public string FirstName { get; set; } = string.Empty;

  [Required, MaxLength(100)]
  public string LastName { get; set; } = string.Empty;
}
