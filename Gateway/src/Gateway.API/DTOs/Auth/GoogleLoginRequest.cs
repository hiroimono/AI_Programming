using System.ComponentModel.DataAnnotations;

namespace Gateway.API.DTOs.Auth;

/// <summary>
/// Incoming payload for Google OAuth login.
/// Frontend sends either an id_token (from GSI) or an authorization code (from redirect flow).
/// </summary>
public class GoogleLoginRequest
{
  /// <summary>Google id_token (used with GSI popup flow).</summary>
  public string? IdToken { get; set; }

  /// <summary>Authorization code (used with redirect/code flow).</summary>
  public string? Code { get; set; }

  /// <summary>Redirect URI used when requesting the code (needed for token exchange).</summary>
  public string? RedirectUri { get; set; }
}
