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
      scuencas=gpd.read_file(path)
      # reproyectar a geograficas
      scuencas.to_crs(epsg='4326',inplace=True)
            
      return scuencas


def download(gdf,landsat_data,banda,scale,codSubcuenca,i_date,f_date):
    # subcuenca_test
    ee_fc=feature2ee(gdf)
    
    # samplear la region
    def rasterExtraction(image):
        feature = image.sampleRegions(collection=ee_fc,scale=scale)
        return feature

    # agregar fecha a la imagen para el map
    def addDate(image):
        img_date = ee.Date(image.date())
        img_date = ee.Number.parse(img_date.format('YYYYMMdd'))
        return image.addBands(ee.Image(img_date).rename('date').toInt())
    
    
      
    results=landsat_data.filterBounds(ee_fc).select(banda).map(addDate)\
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
    df_pivot.to_excel(os.path.join('.','LST_'+list(dict_product.keys())[0]+'_night.xlsx'))
    
    
    # https://stackoverflow.com/questions/46943061/how-to-iterate-over-and-download-each-image-in-an-image-collection-from-the-goog
    # This is OK for small collections
    collectionList = results.toList(results.size())
    collectionSize = collectionList.size().getInfo()
    print(collectionSize)
    for i in range(collectionSize):
        image = ee.Image(collectionList.get(i))
        image_name = image.get('system:index').getInfo()
        print(i)
        print(image_name)
        img_name = "LST_" + str(image_name)
        url = image.getDownloadUrl({
                        'name':img_name,
                        'scale': scale,
                        'crs': 'EPSG:4326',
                        'region': ee_fc.geometry(),
                        'format':"GEO_TIFF",
                        'bands':banda,
                        'filePerBand':True
                    })
        print(url)
        r = requests.get(url, stream=True)
        try:
            folder=os.path.join('..','LST',codSubcuenca)
            os.mkdir(os.path.abspath(folder))
        except:
            pass
        filenameTif = os.path.join(folder,img_name + '.tif')
        with open(filenameTif, "wb") as fd:
                for chunk in r.iter_content(chunk_size=1024):
                    fd.write(chunk)
        fd.close()
        toCelsius(filenameTif)


def product(dict_product,i_date,f_date,banda,scale):
    
    landsat_data=ee.ImageCollection(dict_product.get(list(dict_product.keys())[0]))
    cuencas=load_watershed()
    
    for idx in cuencas.index:
        if idx==cuencas.index[-1]:
            gdf=gpd.GeoDataFrame(cuencas.iloc[-1].explode().geometry[2])
        gdf=gpd.GeoDataFrame(cuencas.loc[idx])
        pass

        try:
            download(landsat_data,gdf,landsat_data,banda,scale,gdf.loc['COD_CUENCA'][0],
                     i_date,f_date)
        except ee.ee_exception.EEException as err:
            if 'Total request size' in str(err):
                print('Caught')

def main():
    os.chdir(r'E:\CIREN\OneDrive - ciren.cl\Ficha_16_Coquimbo\scripts')
    
    # log in gee
    login()
    
    # process
    # sample watersheds
    dict_product={'ERA5':"ECMWF/ERA5/DAILY"}
    i_date='1979-01-02'
    f_date=str(datetime.date.today().strftime("%Y-%m-%d"))
    banda='total_precipitation'
    scale=27830
    
    product(dict_product,i_date,f_date,banda,scale)

if __name__=='__main__':
    main()
    
    
    

