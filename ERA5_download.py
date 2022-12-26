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
    
def getData(gdf,landsat_data,banda,i_date,f_date,ee_fc,scale):
    
    # samplear la region
    def rasterExtraction(image):
        feature=image.sampleRegions(collection=ee_fc,scale=scale)
        return feature
    
    results=landsat_data.filterBounds(ee_fc).select(banda).filterDate(i_date,
                        f_date).map(addDate).map(rasterExtraction).flatten()
    sample_result=results.first().getInfo()
    #extract the properties column from feature collection
    #column order may not be as out sample data order
    
    columns=list(sample_result['properties'].keys())
    #order data columns as per sample data order
    #You can modify this for better optimizaction
    nested_list = results.reduceColumns(ee.Reducer.toList(len(columns)),
                                        columns).values().get(0)
    data=nested_list.getInfo()
    df=pd.DataFrame(data,columns=columns)
    df.index=pd.to_datetime(df['date'],format="%Y%m%d")
    df=df[[x for x in df.columns if x!='date']]
    df_pivot=pd.pivot_table(df,values=banda,index=df.index,columns=df['COD_CUENCA'])
    print(df_pivot.head())
    return df_pivot
    

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
            download(gdf,landsat_data,banda,scale,name,i_date,f_date)
        except ee.ee_exception.EEException as err:
            if 'Total request size' in str(err):
                print('Caught')
#%%
def main():   
    # log in gee
    login()
    
    # chdir
    os.chdir(r'G:\OneDrive - ciren.cl\2022_Ficha_Atacama\06_Scripts')
    
    # process
    # sample watersheds
    dict_product={'ERA5':"ECMWF/ERA5/DAILY"}
    i_date='1992-04-01'
    f_date='2021-03-31'
    banda='total_precipitation'
    scale=27830
    
    product(dict_product,i_date,f_date,banda,scale)

# if __name__=='__main__':
#     main()
    
    
    

