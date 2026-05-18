namespace Gateway.API.Entities;

/// <summary>
/// Represents a chat conversation in the AI Writing Assistant app.
/// </summary>
public class WriterConversation
{
  public Guid Id { get; set; }

  public Guid UserId { get; set; }

  public string Title { get; set; } = string.Empty;

  /// <summary>
  /// How many times the title has been auto-generated (max 3).
  /// </summary>
  public int TitleGenCount { get; set; }

  /// <summary>
  /// If true, the user manually set the title — auto-update stops.
  /// </summary>
  public bool IsTitleManual { get; set; }

  public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

  public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;

  // Navigation properties
  public User User { get; set; } = null!;
  public ICollection<WriterMessage> Messages { get; set; } = [];
}
