using System;
using System.Collections.Generic;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Gateway.API.Migrations
{
    /// <inheritdoc />
    public partial class AddAttachedDocumentIds : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<List<Guid>>(
                name: "AttachedDocumentIds",
                table: "WriterMessages",
                type: "uuid[]",
                nullable: false,
                defaultValueSql: "'{}'::uuid[]");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "AttachedDocumentIds",
                table: "WriterMessages");
        }
    }
}
