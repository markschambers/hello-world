###
library(lubridate)
library(tidyverse)
power <- read.csv("nem_generation_by_fuel_frequent.csv") %>%
  mutate(settlement_date = ymd_hms(settlement_date),
         date_hour = round_date(settlement_date, unit = "hour")) %>%
  filter(settlement_date > ymd_hms("2026-11-18 00:00:00")) %>%
  mutate(date = date(date_hour),
  hour = hour(date_hour)) %>%
  unique()

battery <- power %>%
  filter(fuel_source == "Battery Storage")

ggplot(data = battery) +
geom_line(aes(x = settlement_date, y = total_mw,group = region,color = region)) +
geom_point(aes(x = settlement_date,y = total_mw,color = region)) +
facet_wrap(~region, ncol = 1, scales = "free_y") +
theme_bw() 

battery_hour <- group_by(battery,region,date_hour) %>%
summarise(mean_mw = mean(total_mw))

solar_hour <- filter(power, fuel_source == "Solar") %>%
group_by(date_hour,region) %>%
summarise(mean_mw = mean(total_mw))

rooftop_hour <- filter(power, fuel_source == "Rooftop Solar") %>%
group_by(date_hour,region) %>%
summarise(mean_mw = mean(total_mw))

bat_sol <- bind_rows(solar_hour,rooftop_hour,battery_hour) %>%
group_by(region,date_hour) %>%
summarise(mw = sum(mean_mw))

ggplot(data = bat_sol) +
geom_line(aes(x = date_hour, y = mw,group = region,color = region)) +
geom_point(aes(x = date_hour,y = mw,color = region)) +
facet_wrap(~region, ncol = 1, scales = "free_y") +
theme_bw() 

battery_gam <- mgcv::gam(total_mw ~ s(hour,bs = "cc") + region,data = battery)
plot(battery_gam)

hydro <- power %>%
  filter(fuel_source == "Hydro") %>%
mutate(hour = hour(date_hour),
date = date(date_hour))

  ggplot(data = hydro) +
geom_line(aes(x = date_hour, y = total_mw,group = region,color = region)) +
geom_point(aes(x = date_hour,y = total_mw,color = region)) +
facet_wrap(~region, ncol = 1, scales = "free_y") +
theme_bw() 

#hydro_gam <- mgcv::gam(total_mw ~ s(hour,bs = "cc") + region,data = hydro)

ggsave("hydro_series.png")

solar <- power %>%
  filter(fuel_source == "Solar") 

  ggplot(data = solar) +
geom_line(aes(x = date_hour, y = total_mw,group = region,color = region)) +
geom_point(aes(x = date_hour,y = total_mw,color = region)) +
facet_wrap(~region, ncol = 1, scales = "free_y") +
theme_bw() 

ggsave("solar_series.png")

coal <- filter(power,fuel_source %in% c("Black Coal","Brown Coal")) %>%
group_by(date_hour,region) %>%
summarise(coal_mw = sum(total_mw)) %>%
mutate(hour = hour(date_hour),
date = date(date_hour))

#coal_gam <- mgcv::gam(coal_mw ~ s(hour,bs = "cc") + region,data = coal)

  ggplot(data = coal) +
geom_line(aes(x = date_hour, y = coal_mw,group = region,color = region)) +
geom_point(aes(x = date_hour,y = coal_mw,color = region)) +
facet_wrap(~region, ncol = 1, scales = "free_y") +
theme_bw() 

ggsave("coal_series.png")

gas <- filter(power,fuel_source %in% c("Natural Gas","Natural Gas / Diesel","Natural Gas / Fuel Oil")) %>%
group_by(date_hour,region) %>%
summarise(gas_mw = sum(total_mw)) %>%
mutate(hour = hour(date_hour),
date = date(date_hour))

  ggplot(data = gas) +
geom_line(aes(x = date_hour, y = gas_mw,group = region,color = region)) +
geom_point(aes(x = date_hour,y = gas_mw,color = region)) +
facet_wrap(~region, ncol = 1, scales = "free_y") +
theme_bw() 

rooftop_solar <- filter(power,fuel_source == "Rooftop Solar") %>%
mutate(hour = hour(date_hour),
date = date(date_hour))

rooftop_hour <- group_by(rooftop_solar,date,hour,region) %>%
summarise(mean_mw = mean(total_mw))

  ggplot(data = rooftop_solar) +
geom_line(aes(x = settlement_date, y = total_mw,group = region,color = region)) +
geom_point(aes(x = settlement_date,y = total_mw,color = region)) +
facet_wrap(~region, ncol = 1, scales = "free_y") +
theme_bw() 

ggsave("rooftop_solar.png")

#solar_gam <- mgcv::gam(total_mw ~ s(hour,bs = "cc") + region,
#data = filter(rooftop_solar,region != "SA1"))
#plot(solar_gam)
#sa_solar_gam <- mgcv::gam(total_mw ~ s(hour,bs = "cc") ,
#data = filter(rooftop_solar,region == "SA1"))

#all <- group_by(power,settlement_date) %>%
#summarise(mw = sum(total_mw)) 

#ggplot(data = all) +
#geom_line(aes(x = settlement_date,y = mw)) +
#theme_bw()

wind <- filter(power,fuel_source == "Wind") %>%
mutate(hour = hour(date_hour),
date = date(date_hour))

#wind_gam <- mgcv::gam(total_mw ~ s(hour,bs = "cc") + region,
#data = wind)
#plot(wind_gam)

#wind_qld_gam <- mgcv::gam(total_mw ~ s(hour,bs = "cc"),
#data = filter(wind,region == "QLD1"))

  ggplot(data = wind) +
geom_line(aes(x = date_hour, y = total_mw,group = region,color = region)) +
geom_point(aes(x = date_hour,y = total_mw,color = region)) +
facet_wrap(~region, ncol = 1, scales = "free_y") +
theme_bw() 

ggsave("wind_series.png")