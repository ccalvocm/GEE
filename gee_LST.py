# -*- coding: utf-8 -*-
"""
Created on Tue Oct 25 10:37:47 2022

@author: ccalvo
"""

import ee
import os
import datetime
import pandas as pd

os.chdir(r'C:\Users\ccalvo\Downloads')
service_account = 'gee-276@rigoteo-348620.iam.gserviceaccount.com '
# registrarse en https://signup.earthengine.google.com/#!/service_accounts
folder_json = os.path.join('.','rigoteo-348620-3d55866eac07.json')
credentials = ee.ServiceAccountCredentials(service_account, folder_json)
ee.Initialize(credentials)

# Import the Land Surface Temperature
dict_product={'Landsat9':'LANDSAT/LC09/C02/T1_L2'}
dict_product={'Landsat8':'LANDSAT/LC08/C02/T1_L2'}
dict_product={'MODIS_Terra':'MODIS/061/MOD11A1'}

# Final date of interest (exclusive).
i_date='2021-10-31'
i_date='2013-03-18'
i_date='2000-02-24'
f_date=str(datetime.date.today().strftime("%Y-%m-%d"))
banda='ST_B10'
banda='LST_Day_1km'
scale=30
scale=1e3
# Define the urban location of interest as a point near Lyon, France.

df_est=pd.read_excel(r'G:\ANID_Glaciares\outputs\metadata_estaciones_glaciares.xlsx')
features=[]
for index, row in df_est.iterrows():
#     print(dict(row))
#     construct the geometry from dataframe
    poi_geometry = ee.Geometry.Point([row['Lon'], row['Lat']])
#     print(poi_geometry)
#     construct the attributes (properties) for each point 
    poi_properties = dict(row)
#     construct feature combining geometry and properties
    poi_feature = ee.Feature(poi_geometry, poi_properties)
#     print(poi_feature)
    features.append(poi_feature)

# final Feature collection assembly
ee_fc = ee.FeatureCollection(features)

#%%
def rasterExtraction(image):
    feature = image.sampleRegions(collection=ee_fc,scale=scale)
    return feature

def addDate(image):
    img_date = ee.Date(image.date())
    img_date = ee.Number.parse(img_date.format('YYYYMMdd'))
    return image.addBands(ee.Image(img_date).rename('date').toInt())

def getCelsius(image):
    
    # LST
    #lst = image.select(banda).multiply(0.00341802).add(149.0).add(-273.15)\
    #.rename("LST")
    lst = image.select(banda).multiply(0.02).add(-273.15)\
    .rename("LST")
    image = image.addBands(lst)

    return(image)

landsat_data = ee.ImageCollection(dict_product.get(list(dict_product.keys())[0])) \
    .filterDate(i_date,f_date).map(getCelsius).map(addDate)
  
results=landsat_data.filterBounds(ee_fc).select('LST').map(addDate)\
.map(rasterExtraction).flatten()
sample_result=results.first().getInfo()
#extract the properties column from feature collection
#column order may not be as out sample data order

columns=list(sample_result['properties'].keys())
#order data columns as per sample data order
#You can modify this for better optimizaction
column_df=list(df_est.columns)
column_df.extend(['LST','date'])
nested_list = results.reduceColumns(ee.Reducer.toList(len(column_df)),
                                    column_df).values().get(0)
data = nested_list.getInfo()
df = pd.DataFrame(data, columns=column_df)
df.index=pd.to_datetime(df['date'],format="%Y%m%d")
df=df[[x for x in df.columns if x!='date']]
df_pivot=pd.pivot_table(df,values='LST',index=df.index,columns=df['COD_BNA'])
print(df_pivot.head())
df_pivot.to_excel(os.path.join('.','LST_'+list(dict_product.keys())[0]+'.xlsx'))