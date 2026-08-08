###
library(lubridate)
library(tidyverse)
power <- read.csv("nem_generation_by_fuel.csv") %>%
  mutate(settlement_date = ymd_hms(settlement_date))

battery <- power %>%
  filter(fuel_source == "Battery Storage") 

ggplot(data = battery) +
geom_line(aes(x = settlement_date, y = total_mw,group = region,color = region)) +
geom_point(aes(x = settlement_date,y = total_mw,color = region)) +
facet_wrap(~region) +
theme_bw() 

hydro <- power %>%
  filter(fuel_source == "Hydro") 

  ggplot(data = hydro) +
geom_line(aes(x = settlement_date, y = total_mw,group = region,color = region)) +
geom_point(aes(x = settlement_date,y = total_mw,color = region)) +
facet_wrap(~region) +
theme_bw() 

solar <- power %>%
  filter(fuel_source == "Solar") 

  ggplot(data = solar) +
geom_line(aes(x = settlement_date, y = total_mw,group = region,color = region)) +
geom_point(aes(x = settlement_date,y = total_mw,color = region)) +
facet_wrap(~region) +
theme_bw() 

coal <- filter(power,fuel_source %in% c("Black Coal","Brown Coal")) %>%
group_by(settlement_date,region) %>%
summarise(coal_mw = sum(total_mw))

  ggplot(data = coal) +
geom_line(aes(x = settlement_date, y = coal_mw,group = region,color = region)) +
geom_point(aes(x = settlement_date,y = coal_mw,color = region)) +
facet_wrap(~region) +
theme_bw() 

rooftop_solar <- filter(power,fuel_source == "Rooftop Solar")

  ggplot(data = rooftop_solar) +
geom_line(aes(x = settlement_date, y = total_mw,group = region,color = region)) +
geom_point(aes(x = settlement_date,y = total_mw,color = region)) +
facet_wrap(~region) +
theme_bw() 

wind <- filter(power,fuel_source == "Wind")

  ggplot(data = wind) +
geom_line(aes(x = settlement_date, y = total_mw,group = region,color = region)) +
geom_point(aes(x = settlement_date,y = total_mw,color = region)) +
facet_wrap(~region) +
theme_bw() 

#all <- group_by(power,settlement_date) %>%
#summarise(mw = sum(total_mw)) 

#ggplot(data = all) +
#geom_line(aes(x = settlement_date,y = mw)) +
#theme_bw()