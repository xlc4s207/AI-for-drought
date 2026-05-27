# Direct SEM candidate comparison

This folder compares two compact SHAP-informed direct SEM candidates against the event-aware model.

Candidate A: `Recovery time ~ SHAP top5 predictors`.

Candidate B: `Recovery time ~ SHAP top3 environmental predictors + Duration + Intensity`.

The event-aware model generally retains the highest explanatory power because it includes a broader but still interpretable predictor set. The compact direct candidates are useful for a clearer confirmatory path interpretation.

## R2 comparison

metric,biome,model,rows,holdout_r2,train_r2,predictor_count,features,top5_direct_r2,top5_features,eventaware_r2,gain_vs_top5_direct,gain_vs_eventaware
GPP,Cropland,top3_env_plus_duration_intensity,190590,0.02784496545791626,0.030185937881469727,5,"|EVA|, SSRD, STRD, Duration, Intensity",0.0384859442710876,"|EVA|, SSRD, STRD, PRE, SMrz",0.0764879584312439,-0.010640978813171338,-0.04864299297332764
GPP,Forest,top3_env_plus_duration_intensity,356455,0.05590790510177612,0.059108614921569824,5,"SSRD, |EVA|, STRD, Duration, Intensity",0.0676494836807251,"SSRD, |EVA|, STRD, TMP, SMrz",0.072901964187622,-0.011741578578948975,-0.016994059085845878
GPP,Grassland,top3_env_plus_duration_intensity,393445,0.07886022329330444,0.0790368914604187,5,"SSRD, TMP, VPD, Duration, Intensity",0.0889241695404052,"SSRD, TMP, VPD, |EVA|, PRE",0.163016676902771,-0.01006394624710076,-0.08415645360946655
GPP,Savanna,top3_env_plus_duration_intensity,436636,0.06124246120452881,0.06196993589401245,5,"SSRD, STRD, |EVA|, Duration, Intensity",0.1801512837409973,"SSRD, STRD, |EVA|, TMP, VPD",0.1885738968849182,-0.11890882253646848,-0.1273314356803894
GPP,Shrubland,top3_env_plus_duration_intensity,243279,0.08846402168273926,0.0882490873336792,5,"SSRD, TMP, VPD, Duration, Intensity",0.0989971756935119,"SSRD, TMP, VPD, PRE, Duration",0.1182677149772644,-0.010533154010772636,-0.029803693294525146
RECO,Cropland,top3_env_plus_duration_intensity,217386,0.025632500648498535,0.025944650173187256,5,"|EVA|, SSRD, STRD, Duration, Intensity",0.0381083488464355,"|EVA|, SSRD, STRD, SMrz, VPD",0.135489821434021,-0.012475848197936963,-0.10985732078552246
RECO,Forest,top3_env_plus_duration_intensity,394850,0.08958953619003296,0.08790212869644165,5,"SSRD, |EVA|, TMP, Duration, Intensity",0.093560516834259,"SSRD, |EVA|, TMP, STRD, SMrz",0.0956072807312011,-0.0039709806442260465,-0.0060177445411681435
RECO,Grassland,top3_env_plus_duration_intensity,439163,0.12009215354919434,0.12046325206756592,5,"SSRD, TMP, PRE, Duration, Intensity",0.1200921535491943,"SSRD, TMP, PRE, Intensity, Duration",0.1996886730194091,4.163336342344337e-17,-0.07959651947021476
RECO,Savanna,top3_env_plus_duration_intensity,486666,0.07502961158752441,0.07287991046905518,5,"SSRD, STRD, PRE, Duration, Intensity",0.1872685551643371,"SSRD, STRD, PRE, TMP, |EVA|",0.1975607275962829,-0.11223894357681269,-0.12253111600875849
RECO,Shrubland,top3_env_plus_duration_intensity,293653,0.1416519284248352,0.14234471321105957,5,"SSRD, TMP, PRE, Duration, Intensity",0.1509072184562683,"SSRD, TMP, PRE, WIND, VPD",0.2218310832977295,-0.009255290031433105,-0.08017915487289429
