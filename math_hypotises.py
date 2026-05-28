import numpy as np
import matplotlib.pyplot as plt
import format_score as fs
import math

kp_log = fs.popularity_kp
imdb_log = fs.popularity_score

NOW_YEAR = 2028

START_YEAR = NOW_YEAR - 2010
END_YEAR = NOW_YEAR - 2026 

years = np.arange(END_YEAR, START_YEAR, 1)

k = 100000
b = 40000
def get_mean_score(year: int, k):
    
    return -k/(year+2)+ b
y = get_mean_score(years,k)


y = get_mean_score(years,k)

print(np.round(y))