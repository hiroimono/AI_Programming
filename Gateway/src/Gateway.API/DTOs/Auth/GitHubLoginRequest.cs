using System.ComponentModel.DataAnnotations;

namespace Gateway.API.DTOs.Auth;

/// <summary>
/// Incoming payload for GitHub OAuth login.
/// Frontend sends the authorization code received from GitHub's redirect.
/// </summary>
public class GitHubLoginRequest
{
    [Required]
    public string Code { get; set; } = string.Empty;
}
