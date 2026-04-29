using Microsoft.EntityFrameworkCore;

namespace Gateway.API.Data;

/// <summary>
/// Central database context — all entity DbSets are registered here.
/// EF Core uses this class to generate SQL and manage the DB connection.
/// </summary>
public class AppDbContext : DbContext
{
  public AppDbContext(DbContextOptions<AppDbContext> options) : base(options)
  {
  }

  protected override void OnModelCreating(ModelBuilder modelBuilder)
  {
    base.OnModelCreating(modelBuilder);

    // Entity configurations will be applied here (Fluent API)
    // modelBuilder.ApplyConfigurationsFromAssembly(typeof(AppDbContext).Assembly);
  }
}
