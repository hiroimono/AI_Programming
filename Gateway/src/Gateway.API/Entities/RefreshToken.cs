namespace Gateway.API.Entities;

/// <summary>
/// Persisted refresh token — allows issuing new access tokens without re-login.
/// Stored in DB so it can be explicitly revoked (logout).
/// </summary>
public class RefreshToken
{
  public Guid Id { get; set; }
  public Guid UserId { get; set; }

  /// <summary>
  /// Opaque token string sent to the client (not a JWT).
  /// </summary>
  public string Token { get; set; } = string.Empty;

  public DateTime ExpiresAt { get; set; }
  public DateTime CreatedAt { get; set; }

  /// <summary>
  /// Null until revoked (logout or token rotation).
  /// </summary>
  public DateTime? RevokedAt { get; set; }

  public bool IsExpired => DateTime.UtcNow >= ExpiresAt;
  public bool IsRevoked => RevokedAt is not null;
  public bool IsActive => !IsExpired && !IsRevoked;

  // Navigation
  public User User { get; set; } = null!;
}
