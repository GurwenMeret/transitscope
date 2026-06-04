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

// Isochrone endpoint — appelle OTP via Python
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

// Accessibility endpoint
app.MapGet("/api/accessibility", async (
    double lat,
    double lon,
    string city,
    string time,
    HttpClient http) =>
{
    // Appel vers le script Python via un sous-processus
    // Pour le MVP, retourne des données mockées
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

app.Run();