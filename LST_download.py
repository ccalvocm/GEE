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

def login():
    os.chdir(r'C:\Users\ccalvo\Downloads')
    service_account = 'gee-276@rigoteo-348620.iam.gserviceaccount.com'
    # registrarse en https://signup.earthengine.google.com/#!/service_accounts
    folder_json = os.path.join('.','rigoteo-348620-3d55866eac07.json')
    credentials = ee.ServiceAccountCredentials(service_account, folder_json)
    ee.Initialize(credentials)

def feature2ee(gdf):
    
    #Exception handler
    try:
        
        # box from bounds
        xmin,ymin,xmax,ymax=gdf.buffer(1e-2).total_bounds
        # convert to polygon
        geom=gpd.GeoDataFrame([],geometry=[box(*gdf.total_bounds)])
                
        #for Polygon geo data type
        g = geom.geometry.iloc[0]
        x,y = g.exterior.coords.xy
        cords = np.dstack((x[:-1],y[:-1])).tolist()

        g=ee.Geometry.Polygon(cords)
        feature = ee.Feature(g)
        # features.append(feature)

        ee_object = ee.FeatureCollection(feature)

        return ee_object
    except:
        return None

def load_watershed():
    #check if the file is shapefile or CSV
      path=r'G:\OneDrive - ciren.cl\Of hidrica\AOHIA_ZC\SIG\Mapoteca DGA\Mapoteca_DGA\02_DGA\Cuencas\Cuencas_DARH_2015_SubCuencas.shp'
      scuencas=gpd.read_file(path)
      # reproyectar a geograficas
      scuencas.to_crs(epsg='4326',inplace=True)
            
      return scuencas
  
def load_watershedBNA():
    #check if the file is shapefile or CSV
      path=r'G:\OneDrive - ciren.cl\Of hidrica\AOHIA_ZC\SIG\Mapoteca DGA\Mapoteca_DGA\02_DGA\Cuencas\Cuencas_BNA_Total\Cuencas_BNA_Total.shp'
      scuencas=gpd.read_file(path)
      # reproyectar a geograficas
      scuencas.to_crs(epsg='4326',inplace=True)
            
      return scuencas
             
def load_glaciers():
      path=r'G:\OneDrive - ciren.cl\2021_FONDEF_ID21I10305\Trabajo_de_Campo\02.SIG\Inventario_glaciares_DGA\IPG2022\IPG2022.shp'
      scuencas=gpd.read_file(path)
      # reproyectar a geograficas
      scuencas.to_crs(epsg='4326',inplace=True)
            
      return scuencas

def download(gdf,landsat_data,banda,scale,codcuenca,i_date,f_date):
    # subcuenca_test
    ee_fc=feature2ee(gdf)

    results=landsat_data.filterBounds(ee_fc).select(banda).filterDate(i_date,f_date)
    
    # https://stackoverflow.com/questions/46943061/how-to-iterate-over-and-download-each-image-in-an-image-collection-from-the-goog
    # This is OK for small collections
    collectionList = results.toList(results.size())
    collectionSize = collectionList.size().getInfo()
    for i in range(collectionSize):
        image = ee.Image(collectionList.get(i))
        image_name = image.get('system:index').getInfo()
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
        r = requests.get(url, stream=True)
        folder=os.path.join('..','LST',codcuenca)
        try:
            os.mkdir(os.path.abspath(folder))
        except:
            pass
        filenameTif = os.path.join(folder,img_name + '.tif')
        with open(filenameTif, "wb") as fd:
                for chunk in r.iter_content(chunk_size=1024):
                    fd.write(chunk)
        fd.close()
        toCelsius(filenameTif)

def splitGdf(gdf):

    # box from bounds
    xmin,ymin,xmax,ymax=gdf.total_bounds
    # convert to polygon
    geom=gpd.GeoDataFrame([],geometry=[box(*gdf.total_bounds)])
    

def product(dict_product,i_date,f_date,banda,scale):
    
    landsat_data=ee.ImageCollection(dict_product.get(list(dict_product.keys())[0]))
    glaciares=load_glaciers()
    subcuencasGlaciares=glaciares['COD_CUEN'][(glaciares['COD_CUEN'].str[:2]<='05') & (glaciares['COD_CUEN'].str[:2]>='03')].unique()
    
    for cuenca in subcuencasGlaciares:
        # subCuencaSjoin=cuencaTranslate[cuencaTranslate['COD_SUBC']==subcuenca].sort_values(by='Shape_Area_right',ascending=False)
        # codSubcuenca=subCuencaSjoin.iloc[0]['COD_SCUEN']
        gdf=glaciares[glaciares['COD_CUEN']==cuenca]

        try:
            download(gdf,landsat_data,banda,scale,cuenca,i_date,f_date)
        except ee.ee_exception.EEException as err:
            if 'Total request size' in str(err):
                print('Caught')

def toCelsius(path):
    import rioxarray as rxr
    import numpy as np
    try:
        raster=rxr.open_rasterio(path)
    except:
        os.remove(path)
        return None 

    data2=np.where(raster.data>0, raster.data*0.00341802-124.14999999999998,np.nan)
    raster.data=data2
    raster.rio.to_raster(path.replace('.tif','_celsius.tif'))

def main():
   
    # log in gee
    login()

    # chdir
    os.chdir(r'G:\GEE')
    
    # process
    dict_product={'Landsat8':'LANDSAT/LC08/C02/T1_L2'}
    i_date='2013-03-18'
    f_date=str(datetime.date.today().strftime("%Y-%m-%d"))
    banda='ST_B10'
    scale=30
    
    product(dict_product,i_date,f_date,banda,scale)

if __name__=='__main__':
    main()
    
    
    

