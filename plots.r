###
library(lubridate)
library(tidyverse)
power <- read.csv("nem_generation_by_fuel.csv") %>%
  mutate(settlement_date = ymd_hms(settlement_date)) %>%
  unique()

battery <- power %>%
  filter(fuel_source == "Battery Storage") %>%
mutate(hour = hour(settlement_date))

ggplot(data = battery) +
geom_line(aes(x = settlement_date, y = total_mw,group = region,color = region)) +
geom_point(aes(x = settlement_date,y = total_mw,color = region)) +
facet_wrap(~region, ncol = 1, scales = "free_y") +
theme_bw() 

#battery_gam <- mgcv::gam(total_mw ~ s(hour,bs = "cc") + region,data = battery)

hydro <- power %>%
  filter(fuel_source == "Hydro") %>%
mutate(hour = hour(settlement_date))

  ggplot(data = hydro) +
geom_line(aes(x = settlement_date, y = total_mw,group = region,color = region)) +
geom_point(aes(x = settlement_date,y = total_mw,color = region)) +
facet_wrap(~region, ncol = 1, scales = "free_y") +
theme_bw() 

#hydro_gam <- mgcv::gam(total_mw ~ s(hour,bs = "cc") + region,data = hydro)

ggsave("hydro_series.png")

solar <- power %>%
  filter(fuel_source == "Solar") 

  ggplot(data = solar) +
geom_line(aes(x = settlement_date, y = total_mw,group = region,color = region)) +
geom_point(aes(x = settlement_date,y = total_mw,color = region)) +
facet_wrap(~region, ncol = 1, scales = "free_y") +
theme_bw() 

ggsave("solar_series.png")

coal <- filter(power,fuel_source %in% c("Black Coal","Brown Coal")) %>%
group_by(settlement_date,region) %>%
summarise(coal_mw = sum(total_mw)) %>%
mutate(hour = hour(settlement_date))

#coal_gam <- mgcv::gam(coal_mw ~ s(hour,bs = "cc") + region,data = coal)

  ggplot(data = coal) +
geom_line(aes(x = settlement_date, y = coal_mw,group = region,color = region)) +
geom_point(aes(x = settlement_date,y = coal_mw,color = region)) +
facet_wrap(~region, ncol = 1, scales = "free_y") +
theme_bw() 

ggsave("coal_series.png")

gas <- filter(power,fuel_source %in% c("Natural Gas","Natural Gas / Diesel","Natural Gas / Fuel Oil")) %>%
group_by(settlement_date,region) %>%
summarise(gas_mw = sum(total_mw)) %>%
mutate(hour = hour(settlement_date))

  ggplot(data = gas) +
geom_line(aes(x = settlement_date, y = gas_mw,group = region,color = region)) +
geom_point(aes(x = settlement_date,y = gas_mw,color = region)) +
facet_wrap(~region, ncol = 1, scales = "free_y") +
theme_bw() 

rooftop_solar <- filter(power,fuel_source == "Rooftop Solar") %>%
mutate(hour = hour(settlement_date))

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

wind <- filter(power,fuel_source == "Wind") %>%
mutate(hour = hour(settlement_date))

#wind_gam <- mgcv::gam(total_mw ~ s(hour,bs = "cc") + region,
#data = wind)
#plot(wind_gam)

wind_qld_gam <- mgcv::gam(total_mw ~ s(hour,bs = "cc"),
data = filter(wind,region == "QLD1"))

  ggplot(data = wind) +
geom_line(aes(x = settlement_date, y = total_mw,group = region,color = region)) +
geom_point(aes(x = settlement_date,y = total_mw,color = region)) +
facet_wrap(~region, ncol = 1, scales = "free_y") +
theme_bw() 

ggsave("wind_series.png")

#all <- group_by(power,settlement_date) %>%
#summarise(mw = sum(total_mw)) 

#ggplot(data = all) +
#geom_line(aes(x = settlement_date,y = mw)) +
#theme_bw()