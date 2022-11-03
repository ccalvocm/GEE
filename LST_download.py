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
        xmin,ymin,xmax,ymax=gdf.buffer(1e-3).total_bounds
        # convert to polygon
        geom=gpd.GeoDataFrame([],geometry=[box(*gdf.total_bounds)])
                
        g = [i for i in geom.geometry]
        features=[]
        
        #for Polygon geo data type
        if (geom.geom_type.iloc[0] == 'Polygon'):
            for i in range(len(g)):
                g = [i for i in geom.geometry]
                x,y = g[i].exterior.coords.xy
                cords = np.dstack((x,y)).tolist()

                g=ee.Geometry.Polygon(cords)
                feature = ee.Feature(g)
                features.append(feature)
            print("done")

            ee_object = ee.FeatureCollection(features)

            return ee_object
    except:
        return None

# def getCelsius(image):
    
#     # import rioxarray

#     # raster=rioxarray.open_rasterio(path)
    
#     # with rasterio.open (path, "r+") as img:
#     #     band = np.zeros(shape=(img.width, img.height))

#     # img.write (band, indexes = 7)
    
#     # with rasterio.open(path, "r+") as src:
#     #        src.nodata = np.nan
#     #        print(src.read(masked=True))
#     #        print(src.nodata)
    

#     with rasterio.open(path, "r+") as src:
#         data = src.read((1))
#         data2=np.where(data>0, data*0.00341802-124.14999999999998,data)
#         src.write(data2, indexes = 1)
    
    
#     # LST
#     lst = image.select('ST_B10').multiply(0.00341802).add(149.0).add(-273.15)\
#     .rename("LST")
#     # image = image.addBands(lst)

#     return lst

# def clip(image):
#     feature = image.clip(ee_fc)
#     return feature

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

def download(gdf,landsat_data,banda,scale,codSubcuenca):
    # subcuenca_test
    ee_fc=feature2ee(gdf)

    results=landsat_data.filterBounds(ee_fc).select(banda).filterBounds(ee_fc)
    
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
        img_name = "LANDSAT8_LST_" + str(image_name)
        url = image.getDownloadUrl({
                        'name':img_name,
                        'scale': scale,
                        'crs': 'EPSG:4326',
                        'region': ee_fc.geometry(),
                        'format':"GEO_TIFF"
                    })
        print(url)
        r = requests.get(url, stream=True)
        try:
            folder=os.path.join('.','LST',codSubcuenca)
            os.mkdir(os.path.abspath(folder))
        except:
            pass
        filenameTif = os.path.join(folder,img_name + '.tif')
        with open(filenameTif, "wb") as fd:
                for chunk in r.iter_content(chunk_size=1024):
                    fd.write(chunk)
        fd.close()     

def product(dict_product,i_date,f_date,banda,scale):
    
    landsat_data = ee.ImageCollection(dict_product.get(list(dict_product.keys())[0])) \
    .filterDate(i_date,f_date)
    
    cuencas=load_watershed()
    cuencasBNA=load_watershedBNA()
    glaciares=load_glaciers()
    
    cuencaTranslate=gpd.sjoin(cuencasBNA,cuencas)

    subcuencasGlaciares=glaciares['COD_SCUEN'][(glaciares['COD_SCUEN'].str[:2]<='999') & (glaciares['COD_SCUEN'].str[:2]>='00')].unique()
    
    for subcuenca in subcuencasGlaciares:
        subCuencaSjoin=cuencaTranslate[cuencaTranslate['COD_SUBC']==subcuenca].sort_values(by='Shape_Area_right',ascending=False)
        codSubcuenca=subCuencaSjoin.iloc[0]['COD_SCUEN']
        gdf=cuencas[cuencas['COD_SCUEN']==codSubcuenca]

        try:
            download(gdf,landsat_data,banda,scale,codSubcuenca)
        except ee.ee_exception.EEException as err:
            if 'Total request size' in str(err):
                
                print('Caught')

def main():
    # log in gee
    login()
    
    # process
    dict_product={'Landsat8':'LANDSAT/LC08/C02/T1_L2'}
    i_date='2013-03-18'
    f_date=str(datetime.date.today().strftime("%Y-%m-%d"))
    banda='ST_B10'
    scale=30
    
    product(dict_product,i_date,f_date,banda,scale)

if __name__=='__main__':
    main()
    
    
    

