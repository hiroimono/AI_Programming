namespace Gateway.API.Entities;

/// <summary>
/// Join entity linking a User to an Organization with a specific role.
/// This is the many-to-many relationship table.
/// </summary>
public class Membership
{
  public Guid Id { get; set; }

  public Guid UserId { get; set; }
  public User User { get; set; } = null!;

  public Guid OrganizationId { get; set; }
  public Organization Organization { get; set; } = null!;

  public OrgRole Role { get; set; } = OrgRole.Member;

  public DateTime JoinedAt { get; set; } = DateTime.UtcNow;
}
