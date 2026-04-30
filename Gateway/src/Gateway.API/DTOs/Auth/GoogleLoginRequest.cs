using System.ComponentModel.DataAnnotations;

namespace Gateway.API.DTOs.Auth;

/// <summary>
/// Incoming payload for Google OAuth login.
/// Frontend sends the id_token received from Google Sign-In.
/// </summary>
public class GoogleLoginRequest
{
    [Required]
    public string IdToken { get; set; } = string.Empty;
}
