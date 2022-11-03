from kubernetes import client, config
import time
import requests
import pandas as pd
import logging
import sys
import os
import schedule
import math
from multiprocessing.pool import ThreadPool as Pool


#Creating and Configuring Logger

Log_Format = "%(levelname)s %(asctime)s - %(message)s"
logging.basicConfig(stream = sys.stdout, format = Log_Format, level = logging.INFO)
logger = logging.getLogger()

# Change to loacl while runiing locally  
#config.load_kube_config()
config.load_incluster_config()


kubev1 = client.AppsV1Api()

def getconfig():
    global workloads
    # change this while running locally 
    workloads = pd.read_csv("/mnt/config/workloads.csv")  # map from configs 
#    print(workloads)

getconfig()
schedule.every(10).minutes.do(getconfig)

def gethaproxydata(sname):
    return requests.get(f"http://{os.getenv('PromQL')}/api/v1/query?query={{__name__=~'haproxy_backend_active_servers|haproxy_backend_response_time_average_seconds|haproxy_backend_current_sessions|haproxy_backend_queue_time_average_seconds',proxy=~'.*{sname}.*'}}").json()

global scaletime
lastscaletimedict = {}

def mainloop(workload):
    try:
        # get data 
        hadata = gethaproxydata(workload.workloadName)
        kubedata = kubev1.read_namespaced_deployment_scale(namespace=workload.ns, name=workload.workloadName)
        cursessions = int(hadata['data']['result'][1]['value'][1])
        queueavgtim = float(hadata['data']['result'][2]['value'][1])
        resptime = float(hadata['data']['result'][3]['value'][1])
        backservers = int(hadata['data']['result'][0]['value'][1])
        replicas = int(kubedata.spec.replicas)
        readyreplicas = int(kubedata.status.replicas)
        totalavg = queueavgtim + resptime
        curBaseLine = ( replicas * 2 )

        
        
        # keep last scaled time
        if workload.workloadName in lastscaletimedict.keys():
            lastscaletime = lastscaletimedict[workload.workloadName]
            lastscaled = time.time() - lastscaletime
        else:
            logger.warning(f'Fisrt Loop for  {workload.workloadName}')
            lastscaletimedict[workload.workloadName]=time.time()
            lastscaled = time.time()
        
        # evaluate
        # calculate curSessions baseline
        # curBaseLine = readyreplicas * workload.maxCurPerPod

        #for Debugging
        logger.debug(f"{workload.workloadName} - Last Scaled {lastscaled:.2f} sec ago - Cur: {cursessions}, avgResponseWithQue: {totalavg:.2f}, BackendSrv:\
{backservers}, Replicas: {replicas}, ReadyReplicas: {readyreplicas}")
       
        
        if (replicas == readyreplicas == backservers):
            #Scale Out Condition
            if (cursessions > curBaseLine and replicas < workload.maxReplicas and totalavg > workload.maxReplyTime and lastscaled > workload.stabilizationWindowUp):
                # calculate sugested pod replicas
                # scaleoutvalue = math.ceil(cursessions/workload.maxCurPerPod) if cursessions > curBaseLine else replicas + workload.scaleFactor
                scaleoutvalue = math.ceil( (totalavg/workload.maxReplyTime) * replicas )

                # check for complience
                scaleFactor = scaleoutvalue if scaleoutvalue <  workload.maxReplicas else workload.maxReplicas 

                #make Sure about replicas
                scaleFactor = 2 if ( scaleFactor > 56 or scaleFactor < 2 ) else scaleFactor

                logger.info(f"{workload.workloadName} - SCALING OUT to {scaleFactor} : Last Scaled {lastscaled:.2f} sec ago - Cur: {cursessions},\
avgResponse: {totalavg:.2f}, avgSrvTime: {resptime}, avgQueTime: {queueavgtim}, BackendSrv: {backservers}, Replicas: {replicas}, ReadyReplicas: {readyreplicas}")
                
                lastscaletimedict[workload.workloadName] = time.time()
                kubev1.patch_namespaced_deployment_scale(namespace=workload.ns, name=workload.workloadName, body=[{"op": "replace", "path": "/spec/replicas", "value": scaleFactor}] )
            
            #Scale In Condition
            elif (cursessions < curBaseLine and workload.defReplicas < replicas and totalavg < workload.maxReplyTime and lastscaled > workload.stabilizationWindowDown):      
                # calculate sugested pod replicas
                totalavg = 0.01 if totalavg == 0 else totalavg
                scalinvalue = math.floor( replicas / (workload.maxReplyTime/totalavg))
                
                # check for complience
                scaleFactor = scalinvalue if scalinvalue >  workload.defReplicas else workload.defReplicas

                #make Sure about replicas
                scaleFactor = 2 if ( scaleFactor > 56 or scaleFactor < 2 ) else scaleFactor

                logger.info(f"{workload.workloadName} - SCALING IN to {scaleFactor} : Last Scaled {lastscaled:.2f} sec ago - Cur: {cursessions},\
avgResponse: {totalavg:.2f}, avgSrvTime: {resptime}, avgQueTime: {queueavgtim}, BackendSrv: {backservers}, Replicas: {replicas}, ReadyReplicas: {readyreplicas}")
                
                lastscaletimedict[workload.workloadName] = time.time()
                kubev1.patch_namespaced_deployment_scale(namespace=workload.ns, name=workload.workloadName, body=[{"op": "replace", "path": "/spec/replicas", "value": scaleFactor}] )
    
    except Exception as err:
        logger.error(f"Something went wrong for {workload.workloadName}: {err}")

mainlooppool = Pool(100)

while True:
    # print(lastscaletimedict)
    for index, workload in workloads.iterrows():
        mainlooppool.apply_async(mainloop, (workload,))
    schedule.run_pending()
    time.sleep(1)

