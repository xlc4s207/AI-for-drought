#!/usr/bin/env bash
set -euo pipefail

# 用法:
#   bash extract_merge_merra2_cdo.sh [INPUT_DIR] [OUTPUT_DIR]
# 例子:
#   bash extract_merge_merra2_cdo.sh /data/MERRA2 /home/xulc/flash_drought/gleam/result

INPUT_DIR="${1:-/data/MERRA2}"
OUTPUT_DIR="${2:-/home/xulc/flash_drought/gleam/result}"

RZ_OUT="${OUTPUT_DIR}/SMrz_MERRA2_1/SMrz_MERRA2_1980_2024_daily.nc4"
SF_OUT="${OUTPUT_DIR}/SMs_MERRA2_1/SMs_MERRA2_1980_2024_daily.nc4"

TMP_DIR="${OUTPUT_DIR}/.tmp_merra2_extract"
TMP_RZ="${TMP_DIR}/RZMC"
TMP_SF="${TMP_DIR}/SFMC"
LIST_FILE="${TMP_DIR}/merra2_daily_files.txt"

mkdir -p "${TMP_RZ}" "${TMP_SF}" "$(dirname "${RZ_OUT}")" "$(dirname "${SF_OUT}")"

if ! command -v cdo >/dev/null 2>&1; then
  echo "错误: 未找到 cdo。请先安装 cdo（例如: sudo apt-get install cdo）"
  exit 1
fi

# 仅使用标准日文件名（你已做过去重和规范化）
find "${INPUT_DIR}" -maxdepth 1 -type f -name 'MERRA2_*.tavg1_2d_lnd_Nx.*.nc4' | sort > "${LIST_FILE}"

if [[ ! -s "${LIST_FILE}" ]]; then
  echo "错误: 在 ${INPUT_DIR} 未找到匹配文件 MERRA2_*.tavg1_2d_lnd_Nx.*.nc4"
  exit 1
fi

echo "[1/3] 提取单变量 RZMC / SFMC..."
while IFS= read -r f; do
  b="$(basename "$f")"
  # 只保留单个变量，减小后续合并 I/O 压力
  cdo -L -f nc4c -z zip_4 selname,RZMC "$f" "${TMP_RZ}/${b}"
  cdo -L -f nc4c -z zip_4 selname,SFMC "$f" "${TMP_SF}/${b}"
done < "${LIST_FILE}"

echo "[2/3] 时间融合..."
cdo -L -f nc4c -z zip_4 mergetime "${TMP_RZ}"/*.nc4 "${RZ_OUT}"
cdo -L -f nc4c -z zip_4 mergetime "${TMP_SF}"/*.nc4 "${SF_OUT}"

echo "[3/3] 结果校验..."
echo "RZMC 输出: ${RZ_OUT}"
cdo -s showname "${RZ_OUT}"
cdo -s ntime "${RZ_OUT}"

echo "SFMC 输出: ${SF_OUT}"
cdo -s showname "${SF_OUT}"
cdo -s ntime "${SF_OUT}"

echo "完成。临时目录: ${TMP_DIR}"
echo "如确认无误，可手动删除: rm -rf ${TMP_DIR}"
