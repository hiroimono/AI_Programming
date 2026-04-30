using System.ComponentModel.DataAnnotations;

namespace Gateway.API.DTOs.Auth;

/// <summary>
/// Incoming payload for token refresh.
/// </summary>
public class RefreshRequest
{
  [Required]
  public string RefreshToken { get; set; } = string.Empty;
}
