# -*- coding: utf-8 -*-
"""
Created on Wed Nov  2 22:19:32 2022

@author: Carlos
"""

import ee
import os
import datetime
import pandas as pd
import geopandas as gpd
import numpy as np
import datetime
from shapely.geometry import box
import requests
import geemap
#%%

def login():
    os.chdir(r'C:\Users\ccalvo\Downloads')
    service_account = 'gee-276@rigoteo-348620.iam.gserviceaccount.com'
    # registrarse en https://signup.earthengine.google.com/#!/service_accounts
    folder_json = os.path.join('.','rigoteo-348620-3d55866eac07.json')
    credentials = ee.ServiceAccountCredentials(service_account, folder_json)
    ee.Initialize(credentials)

def feature2ee(gdf):
    """
        # convert to FeatureCollection using one line of code
    Parameters
    ----------
    gdf : TYPE
        DESCRIPTION.

    Returns
    -------
    TYPE
        DESCRIPTION.

    """
    
    return geemap.geopandas_to_ee(gdf)


def load_watershed():
    #check if the file is shapefile or CSV
      path=os.path.join('..','02_SIG','CUENCAS','Cuencas_Atacama.shp')
      scuencas=gpd.read_file(path,encoding='utf-8')
      # reproyectar a geograficas
      scuencas.to_crs(epsg='4326',inplace=True)
            
      return scuencas

# agregar fecha a la imagen para el map
def addDate(image):
    img_date = ee.Date(image.date())
    img_date = ee.Number.parse(img_date.format('YYYYMMdd'))
    return image.addBands(ee.Image(img_date).rename('date').toInt())
    
def getData(landsat_data,banda,i_date,f_date,ee_fc,scale):
    
    def point_mean(img):
        mean = img.reduceRegion(reducer=ee.Reducer.mean(),
                                geometry=ee_fc.geometry(),
                                scale=scale)
        return img.set('date', img.date().format()).set('mean',mean)
    
    bounds = ee_fc.geometry().bounds()
    collection = landsat_data.filterBounds(bounds)
    collectionF = collection.select(banda).filterDate(i_date,f_date)
    
    poi_reduced_imgs = collectionF.map(point_mean)
    
    nested_list = poi_reduced_imgs.reduceColumns(ee.Reducer.toList(2),
                                            ['date','mean']).values().get(0)
    df = pd.DataFrame(nested_list.getInfo(), columns=['date','mean'])
    df['mean']=df['mean'].apply(lambda x: x['total_precipitation'])
    df.set_index('date',inplace=True)  
    df.index=pd.to_datetime(df.index)
    return df

def download(gdf,landsat_data,banda,scale,codSubcuenca,i_date,f_date):
    
    # subcuenca_test
    ee_fc=feature2ee(gdf)
    
    df_return=pd.DataFrame(index=pd.date_range(i_date,f_date),
                           columns=[codSubcuenca])
    
    for delta in df_return.resample('MS').mean().index.month:
        date_end=pd.to_datetime(i_date)+pd.offsets.DateOffset(months=1)
        date_end=date_end.strftime('%Y-%m-%d')
        df_pivot=getData(gdf,landsat_data,banda,i_date,date_end,ee_fc,scale)
        i_date=date_end
        df_return.loc[df_pivot.index]=df_pivot.values
        
    df_pivot.to_excel(os.path.join('.','outputs','pp_ERA5_'+codSubcuenca+'.csv'))

def downloadMon(gdf,landsat_data,banda,scale,codSubcuenca,i_date,f_date):
    
    # subcuenca_test
    ee_fc=feature2ee(gdf)
    
    df_pivot=getData(landsat_data,banda,i_date,f_date,ee_fc,scale)
        
    df_pivot.to_csv(os.path.join('.','outputs','pp_ERA5_'+codSubcuenca+'.csv'))

def product(dict_product,i_date,f_date,banda,scale):
    
    
    landsat_data=ee.ImageCollection(dict_product.get(list(dict_product.keys())[0]))
    cuencas=load_watershed()
    
    for idx in cuencas.index:
        df=pd.DataFrame(np.reshape(cuencas.loc[idx].values,(1,6)),
                        columns=list(cuencas.loc[idx].index),index=[0])
        df=df[[x for x in df.columns if x!='NOM_CUENCA']]
        if idx==cuencas.index[-1]:
            df['geometry']=df['geometry'].loc[0][2]
            gdf=gpd.GeoDataFrame(df)
        else:
            gdf=gpd.GeoDataFrame(df)
        try:
            name=gdf['COD_CUENCA'][0]
            gdf.set_crs(epsg='4326',inplace=True)
            gdf.to_file(os.path.join('.','outputs','cuenca'+name+'.shp'))
            # yearlyMean(gdf,data,banda,scale,name)
            # download(gdf,data,banda,scale,name,i_date,f_date)
            downloadMon(gdf,landsat_data,banda,scale,name,i_date,f_date)
        except ee.ee_exception.EEException as err:
            if 'Total request size' in str(err):
                print('Caught')

def monthlyVals(gdf,data,banda,scale,name,i_date,f_date):
    
    ee_fc=feature2ee(gdf)

    def rasterExtraction(image):
        feature = image.sampleRegions(collection=ee_fc,scale=scale)
        return feature
    
    def addDate(image):
        img_date = ee.Date(image.date())
        img_date = ee.Number.parse(img_date.format('YYYYMMdd'))
        return image.addBands(ee.Image(img_date).rename('date').toInt())
    
    data = data.filterDate(i_date,f_date)
   
    results=data.filterBounds(ee_fc).select(banda).map(addDate)\
    .map(rasterExtraction).flatten()
    sample_result=results.first().getInfo()
    #extract the properties column from feature collection
    #column order may not be as out sample data order
    
    columns=list(sample_result['properties'].keys())
    
    column_df=list(gdf.columns)
    column_df.extend(['total_precipitation','id'])
    nested_list = results.reduceColumns(ee.Reducer.toList(1),
                                        ['total_precipitation']).values().get(0)
    values = nested_list.getInfo()
    df = pd.DataFrame(values, columns=['PP anual (m)'],
                      index=pd.date_range(i_date,f_date,freq='MS'))
    df.to_csv(os.path.join('.','outputs','pp_mean_yr_'+name+'.csv'))
        
def yearlyMean(gdf,data,banda,scale,name):
    startYear = 1991
    endYear = 2021
    years = ee.List.sequence(startYear, endYear, 1)
    
    ee_fc=feature2ee(gdf)
    
    def rasterExtraction(image):
        feature = image.sampleRegions(collection=ee_fc,scale=scale)
        return feature
    
    def FeatureYear(year):
        start = ee.Date.fromYMD(ee.Number(year), 1, 1)
        resul = data \
                         .filterDate(start, start.advance(1,'year')) \
                         .filterBounds(ee_fc.geometry()) \
                         .select(banda) \
                         .sum() \
                         .reduceRegion(
                           reducer=ee.Reducer.mean(),
                           geometry=ee_fc.geometry(),
                           scale=scale
                         )
        return ee.Feature(None, resul)
                
    ra5_2mt = ee.FeatureCollection(years.map(FeatureYear))
        
    #extract the properties column from feature collection
    #column order may not be as out sample data order
    sample_result=ra5_2mt.first().getInfo()
    #extract the properties column from feature collection
    #column order may not be as out sample data order
    
    columns=list(sample_result['properties'].keys())
    
    column_df=list(gdf.columns)
    column_df.extend(['total_precipitation','id'])
    nested_list = ra5_2mt.reduceColumns(ee.Reducer.toList(1),
                                        ['total_precipitation']).values().get(0)
    data = nested_list.getInfo()
    df = pd.DataFrame(data, columns=['PP anual (m)'],
                      index=list(range(startYear,endYear+1)))
    df.to_csv(os.path.join('.','outputs','pp_mean_yr_'+name+'.csv'))

def main():   
    # log in gee
    login()
    
    # chdir
    os.chdir(r'G:\OneDrive - ciren.cl\2022_Ficha_Atacama\06_Scripts')
    
    # process
    # sample watersheds
    # dict_product={'ERA5':"ECMWF/ERA5/MONTHLY"}
    dict_product={'CHIRPS':'UCSB-CHG/CHIRPS/DAILY'}
    i_date='1992-04-01'
    f_date='2021-03-31'
    banda='total_precipitation'
    scale=27830
    
    product(dict_product,i_date,f_date,banda,scale)

# if __name__=='__main__':
#     main()
    
    
    

