# Stage 1: Build
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

# Copy project file and restore dependencies (layer caching)
COPY src/Gateway.API/Gateway.API.csproj src/Gateway.API/
RUN dotnet restore src/Gateway.API/Gateway.API.csproj

# Copy everything else and publish
COPY src/ src/
RUN dotnet publish src/Gateway.API/Gateway.API.csproj -c Release -o /app/publish --no-restore

# Stage 2: Runtime
FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app

# Security: run as non-root user (built-in 'app' user in .NET 8+ images)
USER app

COPY --from=build /app/publish .

# Railway injects PORT env variable
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

ENTRYPOINT ["dotnet", "Gateway.API.dll"]
