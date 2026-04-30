using System.Text;
using Gateway.API.Data;
using Gateway.API.Middleware;
using Gateway.API.Services;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using Scalar.AspNetCore;

var builder = WebApplication.CreateBuilder(args);

// --- Service Registration ---
// Controllers — classes that host API endpoints
builder.Services.AddControllers();

// OpenAPI — generates API documentation (built-in since .NET 9, replaces Swashbuckle)
builder.Services.AddOpenApi();

// EF Core — registers the database context with PostgreSQL (Neon)
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("DefaultConnection")));

// Application services
builder.Services.AddScoped<AuthService>();

// Named HttpClient for GitHub OAuth API calls
builder.Services.AddHttpClient("GitHub", client =>
{
  client.DefaultRequestHeaders.Accept.Add(new("application/json"));
  client.DefaultRequestHeaders.UserAgent.Add(new("Gateway.API", "1.0"));
});

// JWT Authentication
var jwtSection = builder.Configuration.GetSection("Jwt");
var secret = jwtSection["Secret"] ?? throw new InvalidOperationException("Jwt:Secret is not configured");
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
  .AddJwtBearer(options =>
  {
    options.TokenValidationParameters = new TokenValidationParameters
    {
      ValidateIssuer = true,
      ValidateAudience = true,
      ValidateLifetime = true,
      ValidateIssuerSigningKey = true,
      ValidIssuer = jwtSection["Issuer"],
      ValidAudience = jwtSection["Audience"],
      IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(secret))
    };
  });
builder.Services.AddAuthorization();

// YARP Reverse Proxy — routes requests to backend apps based on host/path
builder.Services.AddReverseProxy()
  .LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"));

// CORS — allows the frontend (Angular) to call this backend
builder.Services.AddCors(options =>
{
  options.AddDefaultPolicy(policy =>
  {
    var origins = builder.Configuration.GetSection("AllowedOrigins").Get<string[]>() ?? ["http://localhost:4200"];
    policy.WithOrigins(origins)
            .AllowAnyHeader()
            .AllowAnyMethod()
            .AllowCredentials();
  });
});

var app = builder.Build();

// --- Middleware Pipeline ---
// Development-only: Scalar interactive API docs at /scalar/v1
if (app.Environment.IsDevelopment())
{
  app.MapOpenApi();           // Serves OpenAPI JSON at /openapi/v1.json
  app.MapScalarApiReference(); // Serves Scalar UI at /scalar/v1
}

// Order matters: each request passes through these layers sequentially
app.UseCors();
app.UseAuthentication();  // JWT validation (to be configured in Phase 1)
app.UseAuthorization();   // Role/permission checks
app.MapControllers();

// YARP — proxy unmatched requests to backend apps based on config routes
app.MapReverseProxy(proxyPipeline =>
{
  // Subscription check runs inside the YARP pipeline (only for proxied requests)
  proxyPipeline.UseMiddleware<SubscriptionMiddleware>();
  proxyPipeline.UseSessionAffinity();
  proxyPipeline.UseLoadBalancing();
  proxyPipeline.UsePassiveHealthChecks();
});

// Health check — verifies the service is running in production
app.MapGet("/health", () => Results.Ok(new { status = "healthy", service = "Gateway" }));

app.Run();
