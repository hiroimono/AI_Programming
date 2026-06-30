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

  /// <summary>
  /// Document IDs the user attached to *this* specific message (RAG sources).
  /// Stored as a Postgres uuid[] so the FE can rehydrate the chip row above
  /// the bubble when the conversation is re-opened. Empty list for assistant
  /// messages and for user messages sent without attachments.
  /// </summary>
  public List<Guid> AttachedDocumentIds { get; set; } = [];

  public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

  public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;

  // Navigation property
  public WriterConversation Conversation { get; set; } = null!;
}
