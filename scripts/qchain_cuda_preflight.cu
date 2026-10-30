// GPU provenance/readback preflight. NOT F2/F3/F4 compute parity.
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <vector>
#include <cstdint>
#include <string>
#define CK(x) do { cudaError_t e=(x); if(e!=cudaSuccess){fprintf(stderr,"%s: %s\n",#x,cudaGetErrorString(e));return 2;} } while(0)
__global__ void count_nonzero(const unsigned char* src, size_t n, unsigned long long* sums) {
  size_t idx=blockIdx.x*blockDim.x+threadIdx.x;
  if(idx<n && src[idx]!=0) atomicAdd(sums, 1ULL);
}
int main(int argc,char**argv){
 if(argc!=2){fprintf(stderr,"usage: preflight /path/to/raw\n");return 2;}
 cudaDeviceProp prop{}; CK(cudaGetDeviceProperties(&prop,0));
 printf("GPU=%s compute=%d.%d\n",prop.name,prop.major,prop.minor);
 for(int scene=0;scene<5;scene++){
  for(const char* stage: {"f2-mask","f3-rgba","f4-rgba"}){
   char path[1024]; snprintf(path,sizeof(path),"%s/scene-%02d.%s.bin",argv[1],scene,stage);
   std::ifstream f(path,std::ios::binary);
   if(!f){fprintf(stderr,"missing %s\n",path);return 3;}
   std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(f)),{});
   unsigned long long cpu=0;for(auto v:bytes) cpu+=(v!=0);
   unsigned char* gpu=nullptr; unsigned long long* result=nullptr;unsigned long long got=0;
   CK(cudaMalloc(&gpu,bytes.size()));CK(cudaMalloc(&result,sizeof(got)));
   CK(cudaMemcpy(gpu,bytes.data(),bytes.size(),cudaMemcpyHostToDevice));
   CK(cudaMemset(result,0,sizeof(got)));
   count_nonzero<<<(bytes.size()+255)/256,256>>>(gpu,bytes.size(),result);
   CK(cudaGetLastError());CK(cudaDeviceSynchronize());
   CK(cudaMemcpy(&got,result,sizeof(got),cudaMemcpyDeviceToHost));
   CK(cudaFree(gpu)); CK(cudaFree(result));
   printf("scene=%d stage=%s bytes=%zu cpu_nonzero=%llu gpu_nonzero=%llu match=%s\n",scene,stage,bytes.size(),cpu,got,cpu==got?"true":"false");
   if(cpu!=got)return 4;
  }
 }
 puts("CUDA_DEVICE_REDUCTION_READBACK_PREFLIGHT_PASS; F2_F3_F4_GPU_COMPUTE_NOT_RUN");
 return 0;
}
