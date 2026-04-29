using Gateway.API.Entities;
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

  public DbSet<User> Users => Set<User>();
  public DbSet<Organization> Organizations => Set<Organization>();
  public DbSet<Membership> Memberships => Set<Membership>();

  protected override void OnModelCreating(ModelBuilder modelBuilder)
  {
    base.OnModelCreating(modelBuilder);

    // User configuration
    modelBuilder.Entity<User>(e =>
    {
      e.HasIndex(u => u.Email).IsUnique();
      e.Property(u => u.Email).HasMaxLength(256);
      e.Property(u => u.FirstName).HasMaxLength(100);
      e.Property(u => u.LastName).HasMaxLength(100);
      e.Property(u => u.FullName)
        .HasComputedColumnSql("\"FirstName\" || ' ' || \"LastName\"", stored: true)
        .HasMaxLength(200);
    });

    // Organization configuration
    modelBuilder.Entity<Organization>(e =>
    {
      e.HasIndex(o => o.Slug).IsUnique();
      e.Property(o => o.Name).HasMaxLength(200);
      e.Property(o => o.Slug).HasMaxLength(100);
    });

    // Membership configuration — defines the many-to-many relationship
    modelBuilder.Entity<Membership>(e =>
    {
      e.HasOne(m => m.User)
        .WithMany(u => u.Memberships)
        .HasForeignKey(m => m.UserId)
        .OnDelete(DeleteBehavior.Cascade);

      e.HasOne(m => m.Organization)
        .WithMany(o => o.Memberships)
        .HasForeignKey(m => m.OrganizationId)
        .OnDelete(DeleteBehavior.Cascade);

      // A user can only belong to an organization once
      e.HasIndex(m => new { m.UserId, m.OrganizationId }).IsUnique();
    });
  }
}
