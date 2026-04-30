namespace Gateway.API.DTOs.Auth;

/// <summary>
/// Response returned after successful registration or login.
/// Contains user info but never the password hash.
/// </summary>
public class AuthResponse
{
  public Guid Id { get; set; }
  public string Email { get; set; } = string.Empty;
  public string FullName { get; set; } = string.Empty;
  public string Message { get; set; } = string.Empty;
}
