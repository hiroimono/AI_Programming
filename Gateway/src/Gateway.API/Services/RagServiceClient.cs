using System.IdentityModel.Tokens.Jwt;
using System.Net.Http.Headers;
using System.Security.Claims;
using System.Text;
using Microsoft.IdentityModel.Tokens;

namespace Gateway.API.Services;

/// <summary>
/// Thin client the Gateway uses to reach the shared rag-service for
/// platform-lifecycle operations (currently: cascade-delete a conversation's
/// documents when the conversation itself is deleted).
///
/// The Gateway is the control plane — it owns conversations + quota — so it
/// orchestrates the shared rag-service directly instead of bouncing through an
/// app backend. Every call carries a freshly-minted, short-lived internal JWT
/// (HS256, shared secret) identifying the acting user + app. This is the exact
/// same trust contract the writer backend already uses to call rag-service.
/// </summary>
public class RagServiceClient
{
  // Internal tokens are used immediately and thrown away — 60s is ample and
  // keeps a leaked token's blast radius tiny.
  private const int TokenLifetimeSeconds = 60;

  private readonly HttpClient _http;
  private readonly IConfiguration _config;
  private readonly ILogger<RagServiceClient> _logger;

  public RagServiceClient(HttpClient http, IConfiguration config, ILogger<RagServiceClient> logger)
  {
    _http = http;
    _config = config;
    _logger = logger;
  }

  /// <summary>
  /// Hard-deletes every document a user uploaded to one conversation.
  ///
  /// Best-effort by design: this NEVER throws. On any failure it logs a warning
  /// and returns false so the caller can still delete the conversation itself.
  /// Leftover documents (if the call failed) are reclaimed later by a background
  /// sweep — losing the conversation must never be blocked by a cleanup hiccup.
  /// </summary>
  public async Task<bool> DeleteConversationDocumentsAsync(
    Guid userId, Guid conversationId, CancellationToken cancellationToken = default)
  {
    var secret = _config["Rag:InternalJwtSecret"];
    if (string.IsNullOrEmpty(secret))
    {
      // RAG cleanup isn't configured (e.g. local dev without rag-service).
      // Degrade gracefully: the conversation delete still succeeds.
      _logger.LogDebug(
        "Rag:InternalJwtSecret not set — skipping document cleanup for conversation {ConversationId}",
        conversationId);
      return false;
    }

    try
    {
      var token = MintInternalToken(userId, secret);
      using var request = new HttpRequestMessage(
        HttpMethod.Delete, $"api/documents/by-conversation/{conversationId}");
      request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);

      var response = await _http.SendAsync(request, cancellationToken);
      if (!response.IsSuccessStatusCode)
      {
        _logger.LogWarning(
          "rag-service document cleanup failed for conversation {ConversationId}: HTTP {StatusCode}",
          conversationId, (int)response.StatusCode);
        return false;
      }

      return true;
    }
    catch (Exception ex)
    {
      _logger.LogWarning(
        ex, "rag-service document cleanup errored for conversation {ConversationId}", conversationId);
      return false;
    }
  }

  /// <summary>
  /// Mints a short-lived HS256 internal JWT matching rag-service's claims
  /// contract: iss, sub (= userId), app_id, iat, exp. rag-service verifies the
  /// signature with the same shared secret and scopes every query to
  /// (app_id, user_id) — so a forged user_id in a request body can never win.
  /// </summary>
  private string MintInternalToken(Guid userId, string secret)
  {
    var issuer = _config["Rag:Issuer"] ?? "Gateway.API";
    var appId = _config["Rag:AppId"] ?? "level-2-writer";

    var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(secret));
    var credentials = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);
    var now = DateTime.UtcNow;

    var claims = new List<Claim>
    {
      new(JwtRegisteredClaimNames.Sub, userId.ToString()),
      new("app_id", appId),
    };

    var jwt = new JwtSecurityToken(
      issuer: issuer,
      claims: claims,
      notBefore: now,
      expires: now.AddSeconds(TokenLifetimeSeconds),
      signingCredentials: credentials);

    return new JwtSecurityTokenHandler().WriteToken(jwt);
  }
}
