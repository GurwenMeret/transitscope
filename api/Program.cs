using System.Text.Json;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.AllowAnyOrigin()
              .AllowAnyMethod()
              .AllowAnyHeader();
    });
});

builder.Services.AddHttpClient();

var app = builder.Build();

app.UseCors();

// Health check
app.MapGet("/health", () => Results.Ok(new { status = "ok", version = "1.0.0" }));

// Isochrone endpoint — appelle OTP via GraphQL
app.MapGet("/api/isochrone", async (
    double lat,
    double lon,
    string time,
    int maxMinutes,
    HttpClient http) =>
{
    var otpUrl = $"http://localhost:8080/otp/gtfs/v1";

    var latStr = lat.ToString(System.Globalization.CultureInfo.InvariantCulture);
    var lonStr = lon.ToString(System.Globalization.CultureInfo.InvariantCulture);
    var latDestStr = (lat + 0.01).ToString(System.Globalization.CultureInfo.InvariantCulture);
    var lonDestStr = (lon + 0.01).ToString(System.Globalization.CultureInfo.InvariantCulture);

    var query = $$"""
    {
      plan(
        from: {lat: {{latStr}}, lon: {{lonStr}}}
        to: {lat: {{latDestStr}}, lon: {{lonDestStr}}}
        date: "{{DateTime.Now:yyyy-MM-dd}}"
        time: "{{time}}"
        numItineraries: 3
        transportModes: [
          {mode: BUS},
          {mode: SUBWAY},
          {mode: WALK}
        ]
      ) {
        itineraries {
          duration
          legs {
            mode
            distance
          }
        }
      }
    }
    """;

    var payload = new { query };
    var response = await http.PostAsJsonAsync(otpUrl, payload);

    if (!response.IsSuccessStatusCode)
        return Results.Problem("Erreur OTP");

    var result = await response.Content.ReadFromJsonAsync<object>();
    return Results.Ok(result);
});

// Accessibility endpoint — données mockées
app.MapGet("/api/accessibility", async (
    double lat,
    double lon,
    string city,
    string time,
    HttpClient http) =>
{
    var result = new
    {
        origin = new { lat, lon },
        city,
        time,
        categories = new[]
        {
            new { category = "health", transit = 21.0, bicycle = 12.1, walk = 21.0 },
            new { category = "food",   transit = 3.5,  bicycle = 2.2,  walk = 3.5  },
            new { category = "park",   transit = 22.2, bicycle = 8.9,  walk = 22.2 },
        }
    };
    return Results.Ok(result);
});

// Isochrones précalculés depuis PostGIS
app.MapGet("/api/isochrones/nearest", async (
    double lat,
    double lon,
    int hour,
    int maxMinutes) =>
{
    var connString = app.Configuration.GetConnectionString("Postgres");

    await using var conn = new Npgsql.NpgsqlConnection(connString);
    await conn.OpenAsync();

    var features = new List<object>();
    var modes = new[] { "transit", "bicycle", "walk" };

    foreach (var mode in modes)
    {
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT mode, reachable_points, ST_AsGeoJSON(geom) as geojson
            FROM isochrone_grid
            WHERE city = 'montreal'
              AND mode = @mode
              AND departure_hour = @hour
              AND max_minutes = @maxMinutes
              AND geom IS NOT NULL
            ORDER BY ST_Distance(
                ST_SetSRID(ST_MakePoint(@lon, @lat), 4326)::geography,
                ST_SetSRID(ST_MakePoint(grid_lon, grid_lat), 4326)::geography
            )
            LIMIT 1
        """;

        cmd.Parameters.AddWithValue("mode", mode);
        cmd.Parameters.AddWithValue("hour", hour);
        cmd.Parameters.AddWithValue("maxMinutes", maxMinutes);
        cmd.Parameters.AddWithValue("lat", lat);
        cmd.Parameters.AddWithValue("lon", lon);

        await using var reader = await cmd.ExecuteReaderAsync();
        if (await reader.ReadAsync())
        {
            features.Add(new
            {
                type = "Feature",
                properties = new
                {
                    mode = reader.GetString(0),
                    reachable_points = reader.GetInt32(1),
                },
                geometry = JsonDocument.Parse(reader.GetString(2)).RootElement
            });
        }
    }

    return Results.Ok(new { type = "FeatureCollection", features });
});

app.Run();