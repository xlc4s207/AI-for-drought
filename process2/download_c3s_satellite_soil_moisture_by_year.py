import os
import time
import cdsapi

OUT_DIR = "/data/Copernicus C3S Soil Moisture"
os.makedirs(OUT_DIR, exist_ok=True)

years = [str(y) for y in range(1978, 2027)]
months = [f"{m:02d}" for m in range(1, 13)]
days = [f"{d:02d}" for d in range(1, 32)]

base_request = {
    "variable": [
        "surface_soil_moisture_volumetric",
        "root_zone_soil_moisture_volumetric",
    ],
    "type_of_sensor": ["combined"],
    "time_aggregation": ["daily"],
    "month": months,
    "day": days,
    "version": ["v202505"],
}

record_options = [
    ["cdr", "icdr"],
    ["cdr"],
    ["icdr"],
]

def try_download(client, year: str):
    for records in record_options:
        req = dict(base_request)
        req["year"] = [year]
        req["type_of_record"] = records
        out_file = os.path.join(OUT_DIR, f"satellite_soil_moisture_{year}_{'_'.join(records)}_v202505.zip")
        try:
            print(f"[START] year={year}, records={records}")
            client.retrieve("satellite-soil-moisture", req).download(out_file)
            print(f"[OK] {out_file}")
            return True
        except Exception as exc:
            print(f"[FAIL] year={year}, records={records}, error={exc}")
            time.sleep(2)
    return False


def main():
    client = cdsapi.Client()
    failed = []
    for y in years:
        ok = try_download(client, y)
        if not ok:
            failed.append(y)

    if failed:
        print("FAILED YEARS:", ",".join(failed))
    else:
        print("All years downloaded successfully.")


if __name__ == "__main__":
    main()
