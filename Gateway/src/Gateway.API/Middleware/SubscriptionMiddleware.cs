using System.Security.Claims;
using Yarp.ReverseProxy.Model;

namespace Gateway.API.Middleware;

/// <summary>
/// Runs before YARP forwards the request to a backend app.
/// Ensures the user is authenticated and (in Phase 2) has an active subscription.
/// </summary>
public class SubscriptionMiddleware
{
  private readonly RequestDelegate _next;
  private readonly ILogger<SubscriptionMiddleware> _logger;

  public SubscriptionMiddleware(RequestDelegate next, ILogger<SubscriptionMiddleware> logger)
  {
    _next = next;
    _logger = logger;
  }

  public async Task InvokeAsync(HttpContext context)
  {
    // Only apply to YARP-proxied requests (skip Gateway's own endpoints)
    var proxyFeature = context.GetReverseProxyFeature();
    if (proxyFeature is null)
    {
      await _next(context);
      return;
    }

    // Step 1: Authentication check
    if (context.User.Identity?.IsAuthenticated != true)
    {
      _logger.LogWarning("Unauthenticated request to proxied route: {Path}", context.Request.Path);
      context.Response.StatusCode = StatusCodes.Status401Unauthorized;
      await context.Response.WriteAsJsonAsync(new { message = "Authentication required to access this app" });
      return;
    }

    // Step 2: Extract route info for subscription check
    var routeId = proxyFeature.Route.Config.RouteId;
    var userId = context.User.FindFirst(ClaimTypes.NameIdentifier)?.Value;

    _logger.LogInformation("User {UserId} accessing route {RouteId}", userId, routeId);

    // Phase 2 TODO: Check if user has active subscription for this app
    // var hasAccess = await _subscriptionService.HasAccessAsync(userId, routeId);
    // if (!hasAccess)
    // {
    //     context.Response.StatusCode = StatusCodes.Status403Forbidden;
    //     await context.Response.WriteAsJsonAsync(new { message = "No active subscription for this app" });
    //     return;
    // }

    await _next(context);
  }
}
