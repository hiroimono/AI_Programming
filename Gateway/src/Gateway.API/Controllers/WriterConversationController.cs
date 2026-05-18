using System.Security.Claims;
using Gateway.API.DTOs.Writer;
using Gateway.API.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace Gateway.API.Controllers;

/// <summary>
/// Writer app conversation endpoints: list, create, rename, delete, messages.
/// </summary>
[ApiController]
[Route("api/writer/conversations")]
[Authorize]
public class WriterConversationController : ControllerBase
{
  private readonly WriterConversationService _service;

  public WriterConversationController(WriterConversationService service)
  {
    _service = service;
  }

  private Guid GetUserId() =>
    Guid.Parse(User.FindFirstValue(ClaimTypes.NameIdentifier)!);

  /// <summary>
  /// GET /api/writer/conversations — list all conversations for the current user.
  /// </summary>
  [HttpGet]
  public async Task<IActionResult> GetAll()
  {
    var result = await _service.GetConversationsAsync(GetUserId());
    return Ok(result);
  }

  /// <summary>
  /// GET /api/writer/conversations/search?q=term — search by title or content.
  /// </summary>
  [HttpGet("search")]
  public async Task<IActionResult> Search([FromQuery] string q)
  {
    if (string.IsNullOrWhiteSpace(q))
      return BadRequest(new { message = "Search query is required" });

    var result = await _service.SearchAsync(GetUserId(), q);
    return Ok(result);
  }

  /// <summary>
  /// GET /api/writer/conversations/{id} — get a conversation with messages.
  /// </summary>
  [HttpGet("{id:guid}")]
  public async Task<IActionResult> Get(Guid id)
  {
    var result = await _service.GetConversationAsync(GetUserId(), id);
    if (result is null)
      return NotFound(new { message = "Conversation not found" });
    return Ok(result);
  }

  /// <summary>
  /// POST /api/writer/conversations — create a new conversation.
  /// </summary>
  [HttpPost]
  public async Task<IActionResult> Create([FromBody] CreateConversationRequest request)
  {
    var result = await _service.CreateConversationAsync(GetUserId(), request);
    return CreatedAtAction(nameof(Get), new { id = result.Id }, result);
  }

  /// <summary>
  /// PATCH /api/writer/conversations/{id}/title — rename a conversation (manual).
  /// </summary>
  [HttpPatch("{id:guid}/title")]
  public async Task<IActionResult> UpdateTitle(Guid id, [FromBody] UpdateConversationTitleRequest request)
  {
    var success = await _service.UpdateTitleAsync(GetUserId(), id, request);
    if (!success)
      return NotFound(new { message = "Conversation not found" });
    return Ok(new { message = "Title updated" });
  }

  /// <summary>
  /// DELETE /api/writer/conversations/{id} — delete a single conversation.
  /// </summary>
  [HttpDelete("{id:guid}")]
  public async Task<IActionResult> Delete(Guid id)
  {
    var success = await _service.DeleteConversationAsync(GetUserId(), id);
    if (!success)
      return NotFound(new { message = "Conversation not found" });
    return Ok(new { message = "Conversation deleted" });
  }

  /// <summary>
  /// POST /api/writer/conversations/batch-delete — delete multiple conversations.
  /// </summary>
  [HttpPost("batch-delete")]
  public async Task<IActionResult> BatchDelete([FromBody] BatchDeleteRequest request)
  {
    var count = await _service.BatchDeleteAsync(GetUserId(), request.Ids);
    return Ok(new { message = $"{count} conversation(s) deleted", count });
  }

  /// <summary>
  /// POST /api/writer/conversations/{id}/messages — save a message.
  /// </summary>
  [HttpPost("{id:guid}/messages")]
  public async Task<IActionResult> SaveMessage(Guid id, [FromBody] SaveMessageRequest request)
  {
    var result = await _service.SaveMessageAsync(GetUserId(), id, request);
    if (result is null)
      return NotFound(new { message = "Conversation not found" });
    return CreatedAtAction(nameof(Get), new { id }, result);
  }
}
