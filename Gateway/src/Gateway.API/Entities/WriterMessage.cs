namespace Gateway.API.Entities;

/// <summary>
/// Represents a single message within a WriterConversation.
/// </summary>
public class WriterMessage
{
  public Guid Id { get; set; }

  public Guid ConversationId { get; set; }

  /// <summary>
  /// Message role: "user", "assistant", or "system".
  /// </summary>
  public string Role { get; set; } = string.Empty;

  public string Content { get; set; } = string.Empty;

  public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

  public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;

  // Navigation property
  public WriterConversation Conversation { get; set; } = null!;
}
