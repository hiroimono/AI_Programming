namespace Gateway.API.Entities;

/// <summary>
/// Represents a team or company that groups multiple users together.
/// </summary>
public class Organization
{
  public Guid Id { get; set; }

  public string Name { get; set; } = string.Empty;

  public string Slug { get; set; } = string.Empty;

  public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

  // Navigation property — all users who belong to this organization
  public ICollection<Membership> Memberships { get; set; } = [];
}
