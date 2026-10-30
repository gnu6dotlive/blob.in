/* Private CP-JA7C-B explicit layer; injects a VkResult, never resets the GPU. */
#define _GNU_SOURCE
#include <vulkan/vulkan.h>
#include <vulkan/vk_layer.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
typedef struct Dev {
 VkDevice handle; PFN_vkGetDeviceProcAddr gdpa;
 PFN_vkQueuePresentKHR present;
 PFN_vkCreateSwapchainKHR create_swap;
 PFN_vkDestroySwapchainKHR destroy_swap;
 PFN_vkGetDeviceQueue queue; PFN_vkGetDeviceQueue2 queue2;
 PFN_vkDestroyDevice destroy;
 VkSwapchainKHR primary; unsigned swap_count; uint64_t forwards;
 int injected; unsigned epoch; struct Dev *next;
} Dev;
static Dev *devices;
static PFN_vkGetInstanceProcAddr next_gipa;
static VkInstance root_instance;
static pthread_mutex_t mutex=PTHREAD_MUTEX_INITIALIZER;
static unsigned process_injections;
static unsigned process_device_epochs;
static Dev *get(VkDevice device) {
 for(Dev *d=devices;d;d=d->next) if(d->handle==device) return d;
 return NULL;
}
VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL vkGetInstanceProcAddr(VkInstance,const char*);
VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL vkGetDeviceProcAddr(VkDevice,const char*);
VKAPI_ATTR VkResult VKAPI_CALL vkCreateInstance(const VkInstanceCreateInfo*,
 const VkAllocationCallbacks*,VkInstance*);
VKAPI_ATTR VkResult VKAPI_CALL vkCreateDevice(VkPhysicalDevice,
 const VkDeviceCreateInfo*,const VkAllocationCallbacks*,VkDevice*);
VKAPI_ATTR VkResult VKAPI_CALL vkQueuePresentKHR(VkQueue,const VkPresentInfoKHR*);
VKAPI_ATTR VkResult VKAPI_CALL vkCreateSwapchainKHR(VkDevice,
 const VkSwapchainCreateInfoKHR*,const VkAllocationCallbacks*,VkSwapchainKHR*);
VKAPI_ATTR void VKAPI_CALL vkDestroySwapchainKHR(VkDevice,VkSwapchainKHR,const VkAllocationCallbacks*);
VKAPI_ATTR void VKAPI_CALL vkGetDeviceQueue(VkDevice,uint32_t,uint32_t,VkQueue*);
VKAPI_ATTR void VKAPI_CALL vkGetDeviceQueue2(VkDevice,const VkDeviceQueueInfo2*,VkQueue*);
VKAPI_ATTR void VKAPI_CALL vkDestroyDevice(VkDevice,const VkAllocationCallbacks*);
VKAPI_ATTR VkResult VKAPI_CALL vkNegotiateLoaderLayerInterfaceVersion(VkNegotiateLayerInterface *v) {
 if(!v || v->sType!=LAYER_NEGOTIATE_INTERFACE_STRUCT) return VK_ERROR_INITIALIZATION_FAILED;
 if(v->loaderLayerInterfaceVersion>2)v->loaderLayerInterfaceVersion=2;
 v->pfnGetInstanceProcAddr=vkGetInstanceProcAddr;
 v->pfnGetDeviceProcAddr=vkGetDeviceProcAddr;
 v->pfnGetPhysicalDeviceProcAddr=NULL;
 fprintf(stderr,"CPJA7CB_LOADER_NEGOTIATED interface=%u\n",v->loaderLayerInterfaceVersion);
 return VK_SUCCESS;
}
VKAPI_ATTR VkResult VKAPI_CALL vkCreateInstance(const VkInstanceCreateInfo*ci,
 const VkAllocationCallbacks*a,VkInstance *out) {
 VkLayerInstanceCreateInfo *link=NULL;
 for(VkLayerInstanceCreateInfo *p=(void*)ci->pNext;p;p=(void*)p->pNext)
  if(p->sType==VK_STRUCTURE_TYPE_LOADER_INSTANCE_CREATE_INFO &&
     p->function==VK_LAYER_LINK_INFO){link=p;break;}
 if(!link || !link->u.pLayerInfo) return VK_ERROR_INITIALIZATION_FAILED;
 PFN_vkGetInstanceProcAddr next=link->u.pLayerInfo->pfnNextGetInstanceProcAddr;
 PFN_vkCreateInstance create=(PFN_vkCreateInstance)next(NULL,"vkCreateInstance");
 if(!create)return VK_ERROR_INITIALIZATION_FAILED;
 link->u.pLayerInfo=link->u.pLayerInfo->pNext;
 VkResult result=create(ci,a,out);
 if(result==VK_SUCCESS){next_gipa=next;root_instance=*out;
  fprintf(stderr,"CPJA7CB_INSTANCE_CREATED loader_chain=1\n");}
 return result;
}
VKAPI_ATTR VkResult VKAPI_CALL vkCreateDevice(VkPhysicalDevice physical,
 const VkDeviceCreateInfo*ci,const VkAllocationCallbacks*a,VkDevice*out) {
 VkLayerDeviceCreateInfo *link=NULL;
 for(VkLayerDeviceCreateInfo*p=(void*)ci->pNext;p;p=(void*)p->pNext)
  if(p->sType==VK_STRUCTURE_TYPE_LOADER_DEVICE_CREATE_INFO &&
     p->function==VK_LAYER_LINK_INFO){link=p;break;}
 if(!link || !link->u.pLayerInfo)return VK_ERROR_INITIALIZATION_FAILED;
 PFN_vkGetInstanceProcAddr gipa=link->u.pLayerInfo->pfnNextGetInstanceProcAddr;
 PFN_vkGetDeviceProcAddr gdpa=link->u.pLayerInfo->pfnNextGetDeviceProcAddr;
 PFN_vkCreateDevice create=(PFN_vkCreateDevice)gipa(root_instance,"vkCreateDevice");
 if(!create)create=(PFN_vkCreateDevice)gipa(NULL,"vkCreateDevice");
 if(!create||!gdpa)return VK_ERROR_INITIALIZATION_FAILED;
 link->u.pLayerInfo=link->u.pLayerInfo->pNext;
 VkResult result=create(physical,ci,a,out);
 if(result!=VK_SUCCESS)return result;
 Dev*d=calloc(1,sizeof(*d));if(!d)return VK_ERROR_OUT_OF_HOST_MEMORY;
 d->handle=*out;d->gdpa=gdpa;
 d->present=(PFN_vkQueuePresentKHR)gdpa(*out,"vkQueuePresentKHR");
 d->create_swap=(PFN_vkCreateSwapchainKHR)gdpa(*out,"vkCreateSwapchainKHR");
 d->destroy_swap=(PFN_vkDestroySwapchainKHR)gdpa(*out,"vkDestroySwapchainKHR");
 d->queue=(PFN_vkGetDeviceQueue)gdpa(*out,"vkGetDeviceQueue");
 d->queue2=(PFN_vkGetDeviceQueue2)gdpa(*out,"vkGetDeviceQueue2");
 d->destroy=(PFN_vkDestroyDevice)gdpa(*out,"vkDestroyDevice");
 if(!d->destroy||!d->queue) {
  fprintf(stderr,"CPJA7CB_DISPATCH_UNAVAILABLE\n");free(d);
  return VK_ERROR_INITIALIZATION_FAILED;
 }
 pthread_mutex_lock(&mutex);d->epoch=++process_device_epochs;
 d->next=devices;devices=d;pthread_mutex_unlock(&mutex);
 fprintf(stderr,"CPJA7CB_DEVICE_CREATED dispatch=1 device_epoch=%u\n",d->epoch);
 return VK_SUCCESS;
}
VKAPI_ATTR VkResult VKAPI_CALL vkCreateSwapchainKHR(VkDevice dev,
 const VkSwapchainCreateInfoKHR*ci,const VkAllocationCallbacks*a,VkSwapchainKHR*out) {
 pthread_mutex_lock(&mutex);Dev*d=get(dev);pthread_mutex_unlock(&mutex);
 if(!d)return VK_ERROR_INITIALIZATION_FAILED;
 VkResult r=d->create_swap(dev,ci,a,out);
 if(r==VK_SUCCESS){
  pthread_mutex_lock(&mutex);d->swap_count++;
  if(d->swap_count==1)d->primary=*out;
  unsigned n=d->swap_count;pthread_mutex_unlock(&mutex);
  fprintf(stderr,"CPJA7CB_SWAPCHAIN_CREATED ordinal=%u\n",n);
 }
 return r;
}
VKAPI_ATTR void VKAPI_CALL vkDestroySwapchainKHR(VkDevice dev,VkSwapchainKHR sc,
 const VkAllocationCallbacks*a) {
 pthread_mutex_lock(&mutex);Dev*d=get(dev);pthread_mutex_unlock(&mutex);
 if(d&&d->destroy_swap)d->destroy_swap(dev,sc,a);
}
VKAPI_ATTR void VKAPI_CALL vkGetDeviceQueue(VkDevice dev,uint32_t family,
 uint32_t idx,VkQueue*out){
 pthread_mutex_lock(&mutex);Dev*d=get(dev);pthread_mutex_unlock(&mutex);
 if(d&&d->queue)d->queue(dev,family,idx,out);
}
VKAPI_ATTR void VKAPI_CALL vkGetDeviceQueue2(VkDevice dev,
 const VkDeviceQueueInfo2*info,VkQueue*out) {
 pthread_mutex_lock(&mutex);Dev*d=get(dev);pthread_mutex_unlock(&mutex);
 if(d&&d->queue2)d->queue2(dev,info,out);
}
static uint64_t present_id(const VkPresentInfoKHR*info,uint32_t i) {
 for(const VkBaseInStructure*p=(void*)info->pNext;p;p=p->pNext)
  if(p->sType==VK_STRUCTURE_TYPE_PRESENT_ID_KHR){
   const VkPresentIdKHR*ids=(void*)p;
   return ids->pPresentIds&&i<ids->swapchainCount?ids->pPresentIds[i]:0;
  }
 return 0;
}
VKAPI_ATTR VkResult VKAPI_CALL vkQueuePresentKHR(VkQueue queue,const VkPresentInfoKHR*info) {
 pthread_mutex_lock(&mutex);
 /* This private layer is allowed in a single test viewer process only. */
 Dev*d=devices;
 if(!d){pthread_mutex_unlock(&mutex);return VK_ERROR_INITIALIZATION_FAILED;}
 const char *mode=getenv("CPJA7CB_LOADER_FAULT");
 int one=mode && !strcmp(mode,"primary-id-41");
 int two=mode && !strcmp(mode,"primary-twice");
 const char *shared=getenv("CPJA7CB_PROCESS_LOSS_COUNT");
 unsigned prior=shared?(unsigned)atoi(shared):0;
 int fault=0;uint64_t target=0;
 if(info&&!d->injected&&(one||two))
  for(uint32_t i=0;i<info->swapchainCount;i++){
   uint64_t id=present_id(info,i);
   int first=(id==41 && prior==0);
   int second=(two && id==5 && prior==1);
   if(info->pSwapchains[i]==d->primary&&(first||second)){
    char next_count[12];
    snprintf(next_count,sizeof(next_count),"%u",prior+1);
    if(setenv("CPJA7CB_PROCESS_LOSS_COUNT",next_count,1)!=0)break;
    d->injected=1;process_injections++;fault=1;target=id;break;
   }
  }
 PFN_vkQueuePresentKHR forward=d->present;
 if(!fault)d->forwards++;
 uint64_t forwarded=d->forwards;
 pthread_mutex_unlock(&mutex);
 if(fault) {
  fprintf(stderr,
   "CPJA7CB_LOADER_INJECTED_VK_ERROR_DEVICE_LOST primary=1 present_id=%" PRIu64 " dispatch=vkGetDeviceProcAddr synthetic=1\n",target);
  return VK_ERROR_DEVICE_LOST;
 }
 if(forwarded==1)fprintf(stderr,"CPJA7CB_LOADER_FIRST_FORWARD success_path=1\n");
 return forward(queue,info);
}
VKAPI_ATTR void VKAPI_CALL vkDestroyDevice(VkDevice dev,const VkAllocationCallbacks*a){
 pthread_mutex_lock(&mutex);Dev **p=&devices;
 while(*p&&(*p)->handle!=dev)p=&(*p)->next;
 Dev*d=*p;if(d)*p=d->next;pthread_mutex_unlock(&mutex);
 if(d){
  fprintf(stderr,"CPJA7CB_DEVICE_DESTROYED forwarded=%" PRIu64 " injected=%d\n",d->forwards,d->injected);
  d->destroy(dev,a);free(d);
 }
}
VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL vkGetDeviceProcAddr(VkDevice dev,const char*name){
 if(!name)return NULL;
 if(!strcmp(name,"vkGetDeviceProcAddr"))return (PFN_vkVoidFunction)vkGetDeviceProcAddr;
 if(!strcmp(name,"vkQueuePresentKHR"))return (PFN_vkVoidFunction)vkQueuePresentKHR;
 if(!strcmp(name,"vkCreateSwapchainKHR"))return (PFN_vkVoidFunction)vkCreateSwapchainKHR;
 if(!strcmp(name,"vkDestroySwapchainKHR"))return (PFN_vkVoidFunction)vkDestroySwapchainKHR;
 if(!strcmp(name,"vkGetDeviceQueue"))return (PFN_vkVoidFunction)vkGetDeviceQueue;
 if(!strcmp(name,"vkGetDeviceQueue2"))return (PFN_vkVoidFunction)vkGetDeviceQueue2;
 if(!strcmp(name,"vkDestroyDevice"))return (PFN_vkVoidFunction)vkDestroyDevice;
 pthread_mutex_lock(&mutex);Dev*d=get(dev);pthread_mutex_unlock(&mutex);
 return d?d->gdpa(dev,name):NULL;
}
VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL vkGetInstanceProcAddr(VkInstance inst,const char*name){
 if(!name)return NULL;
 if(!strcmp(name,"vkGetInstanceProcAddr"))return (PFN_vkVoidFunction)vkGetInstanceProcAddr;
 if(!strcmp(name,"vkGetDeviceProcAddr"))return (PFN_vkVoidFunction)vkGetDeviceProcAddr;
 if(!strcmp(name,"vkCreateInstance"))return (PFN_vkVoidFunction)vkCreateInstance;
 if(!strcmp(name,"vkCreateDevice"))return (PFN_vkVoidFunction)vkCreateDevice;
 if(!strcmp(name,"vkQueuePresentKHR"))return (PFN_vkVoidFunction)vkQueuePresentKHR;
 if(!strcmp(name,"vkDestroyDevice"))return (PFN_vkVoidFunction)vkDestroyDevice;
 if(!strcmp(name,"vkGetDeviceQueue"))return (PFN_vkVoidFunction)vkGetDeviceQueue;
 if(!strcmp(name,"vkGetDeviceQueue2"))return (PFN_vkVoidFunction)vkGetDeviceQueue2;
 if(!strcmp(name,"vkCreateSwapchainKHR"))return (PFN_vkVoidFunction)vkCreateSwapchainKHR;
 if(!strcmp(name,"vkDestroySwapchainKHR"))return (PFN_vkVoidFunction)vkDestroySwapchainKHR;
 return next_gipa?next_gipa(inst,name):NULL;
}
