rm(list=ls());gc()
library(data.table)
library(ncdf4)
library(parallel)
library(magrittr)

# Function to calculate characteristics of a single 4D drought event
calculate_event <- function(i,year,txt_path,smi_ncpath,smb_ncpath,path){
  # Load necessary libraries
  library(data.table)
  library(ncdf4)
  library(dplyr)
  library(magrittr)
  library(abind)
  # Construct lon-lat grid and land mask
  lonlat <- expand.grid(lon=seq(-179.5,179.5,1),
                        lat=seq(-89.5,89.5,1))
  sst <- read.table(paste0(path,'/map_mask_filter.txt'))
  land <- which(as.matrix(sst) %>% c==1)
  lonlat$sst <- c(as.matrix(sst))
  lonlat$order <- 1:nrow(lonlat)
  lonlat$threshold1 <- NA
  lonlat$threshold2 <- NA
  lonlat$threshold3 <- NA
  # Load soil moisture drought thresholds for each layer
  # The RData file for threshold is a two-column matrix containing the thresholds calculated from the 90th and 80th percentiles. 
  # Here, we use the 90th percentile.
  load(paste0(path,"/drought_threshold/threshold1.RData"))
  threshold <- threshold[,1] %>% c
  lonlat$threshold1[which(lonlat$sst==1)] <- threshold
  load(paste0(path,"/drought_threshold/threshold2.RData"))
  threshold <- threshold[,1] %>% c
  lonlat$threshold2[which(lonlat$sst==1)] <- threshold
  load(paste0(path,"/drought_threshold/threshold3.RData"))
  threshold <- threshold[,1] %>% c
  lonlat$threshold3[which(lonlat$sst==1)] <- threshold
  # Reconstruct 3D threshold matrix: lon × lat × depth
  threshold <- list(
    matrix(lonlat$threshold1,ncol=180,nrow=360) %>% .[,31:180],
    matrix(lonlat$threshold2,ncol=180,nrow=360) %>% .[,31:180],
    matrix(lonlat$threshold3,ncol=180,nrow=360) %>% .[,31:180]
  ) %>% abind(.,along=3)
  rm(lonlat,sst,land);gc()
  # Layer weighting
  lay <- c(7,21,72)
  # Load one event’s .txt file: columns = day, x_idx, y_idx, z_idx
  d <- read.table(paste0(txt_path,"/",i,".txt")) %>% as.data.table
  d$day <- d$V1
  d$lon <- seq(-179.5,179.5,1)[d$V2]
  d$lat <- seq(-59.5,89.5,1)[d$V3]
  d$layer <- d$V4
  d$loc <- paste0(d$lon,',',d$lat)
  # Load precomputed latitude-based grid cell area (in km²)
  area_lat <- c(107.775624413856, 323.293382700031, 538.710681395359, 753.960587542986, 968.976228310691, 1183.69081497893,
                1398.03766686724, 1611.95023518156, 1825.36212676526, 2038.20712773693,2250.41922699783, 2461.93263959285, 
                2672.68182990838, 2882.6015346914, 3091.62678587404, 3299.69293318859,3506.73566655815, 3712.69103824847, 
                3917.49548476742, 4121.08584849837, 4323.39939905497, 4524.37385434481, 4723.94740133036, 4922.05871647586, 
                5118.64698586977, 5313.65192501263,5507.01379826111, 5698.67343791943, 5888.57226297016, 6076.65229743679,
                6262.85618837152, 6447.1272234619, 6629.40934825097, 6809.64718296607, 6987.78603895211, 7163.77193470577,
                7337.55161150785, 7509.07254865139, 7678.28297826414, 7845.13189972418,8009.56909366852, 8171.54513559479, 
                8331.0114090568, 8487.92011845541, 8642.2243014266, 8793.87784082912,8942.8354763348, 9089.05281562472, 
                9232.48634519549, 9373.09344077963,9510.83237738504, 9645.66233895871, 9777.54342768, 9906.43667288967, 
                10032.3040396606, 10155.1084370167,10274.8137258071, 10391.3847262419, 10504.7872250978, 10614.9879825991,
                10721.9547389842, 10825.6562207627, 10926.0621466725, 11023.1432333443, 11116.8712006804, 11207.2187769577,
                11294.1597036605, 11377.6687400526, 11457.7216674956, 11534.2952935211,11607.3674556651, 11676.9170250703, 
                11742.9239098661, 11805.3690583309, 11864.2344618444, 11919.5031576378,11971.1592313456, 12019.1878193681, 
                12063.5751110476, 12104.3083506663,12141.3758392686, 12174.7669363153, 12204.4720611718, 12230.4826944356, 
                12252.7913791073, 12271.391721607,12286.2783926404, 12297.4471279166, 12304.8947287194, 12308.6190623347) %>% rev
  area_lat <- c(rev(area_lat),area_lat)[31:180]
  d$area <- area_lat[d$V3]
  # Reorganize and prepare input
  d <- d[,c("day","lon","lat","loc","layer","V2","V3","area")]
  d0 <- sort(unique(d$day))
  # Loop over each day and each layer to extract soil moisture deficits
  d <- lapply(d0, function(j){
    d1 <- subset(d,day==j)
    lapply(unique(d1$layer), function(k){
      d2 <- subset(d1,layer==k)
      fi <- paste0(smi_ncpath,"/swvl",k,"_",j+120,".nc")
      nc <- nc_open(fi)
      smi <- ncvar_get(nc,paste0("swvl",k))
      smi <- (threshold[,,k]-smi[,31:180])*100
      nc_close(nc);rm(nc)
      d2$smi <- sapply(1:nrow(d2),function(l){
        smi[d2$V2[l],d2$V3[l]]
      })
      d2$smi[which(d2$smi<0)] <- NA
      d2
    }) %>% rbindlist
  })
  names(d) <- d0
  # Generate date labels
  date <- seq.Date(from = as.Date("1981-01-01"), to = as.Date("1981-12-31"), by = "day") %>% as.character %>% substring(.,6,10)
  # Analyze number of layers involved each day
  time_cycle <- lapply(d, function(x){x$layer %>% unique %>% sort})
  # Calculate daily area of each layer (3D shape analysis)
  area_cycle <- lapply(d, function(x){
    y <- sapply(1:3, function(j){
      subset(x,layer==j) %>% .$area %>% sum
    })
    y[which(y==0)] <- NA
    y
  })
  # Count how many days each layer appears
  time_num <- time_cycle %>% unlist %>% table %>% as.data.frame
  time <- rep(0,3)
  time[as.numeric(as.character(time_num[,1]))] <- time_num$Freq
  # classification
  area_max1 <- sapply(1:length(area_cycle), function(j){
    a1 <- mean(area_cycle[[j]][1:2],na.rm=T)
    a2 <- mean(area_cycle[[j]][3],na.rm=T)
    if(is.na(a1)){return(2)}
    if(is.na(a2)){return(1)}
    if(a1==a2){
      return(0)
    }else if(a1>a2){
      return(1)
    }else{
      return(2)
    }
  })
  if(length(which(area_max1==1))>(0.6*length(area_cycle))){
    tag1 <- "intriangle"
  }else if(length(which(area_max1==2))>(0.6*length(area_cycle))){
    tag1 <- "triangle"
  }else{
    tag1 <- "column"
  }
  # Final date range
  date <- paste0(year,"-",date)
  date <- date[121:273]
  start_date <- date[d0[1]]
  end_date <- date[d0[length(d0)]]
  # Return drought event characteristics and time series data
  list(
    data=d,
    event=list(
      tag1=tag1,
      year=year,
      start=d0[1],
      end=d0[length(d0)],
      start_date=start_date,
      end_date=end_date,
      duration=length(d),
      maximum_area=rbindlist(d)[,c("loc","area")] %>% distinct %>% .$area %>% sum(.,na.rm=T),
      intensity=sapply(1:3,function(j){
        weighted.mean(rbindlist(d) %>% subset(.,layer==j) %>% .$smi,rbindlist(d)%>% subset(.,layer==j) %>% .$area,na.rm=T)
      }) %>% weighted.mean(.,w=lay,na.rm=T)
    )
  ) %>% return
}

year <- 1981 # Set the year to analyze
path <- "/data/users/guan/CV/data" # Define base path where all input/output data are stored
dir.create(paste0(path,"/characteristic")) # Create an output directory for storing event-level characteristics

# Define paths for netCDF soil moisture input and boolean mask input
smi_ncpath <- paste0(path,"/sm/")  # raw soil moisture (swvl1~3)
smb_ncpath <- paste0(path,"/sm_bool/") # binary drought mask (optional input)
# Path to .txt files containing drought tracks (output from cc3d+tracker)
txt_path <- paste0(path,"/cluster2/")

cl <- makeCluster(8) # Launch parallel computing environment using 8 cores
# Run calculate_event() for each .txt file in parallel using parLapply
# Each file represents a single 3D drought event to analyze
event_characteristic <- parLapply(cl, 1:length(dir( paste0(path,"/cluster2/"))),# total number of events
                                  calculate_event,year=year,txt_path=txt_path,
                                  smi_ncpath=smi_ncpath,smb_ncpath=smb_ncpath,path=path)
# Save the full list of event characteristics as a single .RData object
save(event_characteristic,file = paste0(path,"/characteristic/",year,".RData"))
stopCluster(cl) # Shut down the parallel cluster to free system resources
gc()
