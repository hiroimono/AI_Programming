namespace Gateway.API.Entities;

/// <summary>
/// Represents a registered user in the platform.
/// </summary>
public class User
{
  public Guid Id { get; set; }

  public string Email { get; set; } = string.Empty;

  /// <summary>
  /// Null for users who registered via external providers (Google, GitHub).
  /// </summary>
  public string? PasswordHash { get; set; }

  public string FirstName { get; set; } = string.Empty;

  public string LastName { get; set; } = string.Empty;

  // Computed column — auto-generated from FirstName + LastName in the database
  public string FullName { get; set; } = string.Empty;

  public bool EmailConfirmed { get; set; }

  public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

  public DateTime? LastLoginAt { get; set; }

  // Navigation property — all organizations this user belongs to
  public ICollection<Membership> Memberships { get; set; } = [];
}
