import cdsapi

output_file = "/data/Copernicus C3S Soil Moisture/satellite_soil_moisture_1978_2026_v202505.zip"

dataset = "satellite-soil-moisture"
request = {
    "variable": [
        "surface_soil_moisture_volumetric",
        "root_zone_soil_moisture_volumetric",
    ],
    "type_of_sensor": ["combined"],
    "time_aggregation": ["daily"],
    "year": [
        "1978", "1979", "1980", "1981", "1982", "1983", "1984", "1985", "1986", "1987",
        "1988", "1989", "1990", "1991", "1992", "1993", "1994", "1995", "1996", "1997",
        "1998", "1999", "2000", "2001", "2002", "2003", "2004", "2005", "2006", "2007",
        "2008", "2009", "2010", "2011", "2012", "2013", "2014", "2015", "2016", "2017",
        "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026",
    ],
    "month": ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"],
    "day": [
        "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
        "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
        "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31",
    ],
    "type_of_record": ["icdr", "cdr"],
    "version": ["v202505"],
}

client = cdsapi.Client()
client.retrieve(dataset, request).download(output_file)
print(f"Downloaded: {output_file}")
