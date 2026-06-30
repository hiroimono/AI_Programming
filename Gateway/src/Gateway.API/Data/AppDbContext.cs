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
  public DbSet<RefreshToken> RefreshTokens => Set<RefreshToken>();
  public DbSet<WriterConversation> WriterConversations => Set<WriterConversation>();
  public DbSet<WriterMessage> WriterMessages => Set<WriterMessage>();

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

    // RefreshToken configuration
    modelBuilder.Entity<RefreshToken>(e =>
    {
      e.HasIndex(rt => rt.Token).IsUnique();
      e.Property(rt => rt.Token).HasMaxLength(256);

      e.HasOne(rt => rt.User)
        .WithMany()
        .HasForeignKey(rt => rt.UserId)
        .OnDelete(DeleteBehavior.Cascade);
    });

    // WriterConversation configuration
    modelBuilder.Entity<WriterConversation>(e =>
    {
      e.Property(c => c.Title).HasMaxLength(200);
      e.HasIndex(c => new { c.UserId, c.UpdatedAt });

      e.HasOne(c => c.User)
        .WithMany()
        .HasForeignKey(c => c.UserId)
        .OnDelete(DeleteBehavior.Cascade);
    });

    // WriterMessage configuration
    modelBuilder.Entity<WriterMessage>(e =>
    {
      e.Property(m => m.Role).HasMaxLength(20);
      e.HasIndex(m => m.ConversationId);

      // Persist per-message RAG attachments as a native uuid[] column. The
      // FE rehydrates these on conversation load so chip rows stay anchored
      // to the user message they were originally sent with.
      e.Property(m => m.AttachedDocumentIds)
        .HasColumnType("uuid[]")
        .HasDefaultValueSql("'{}'::uuid[]");

      e.HasOne(m => m.Conversation)
        .WithMany(c => c.Messages)
        .HasForeignKey(m => m.ConversationId)
        .OnDelete(DeleteBehavior.Cascade);
    });
  }
}
