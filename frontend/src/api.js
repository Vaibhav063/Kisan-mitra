const base=import.meta.env.VITE_API_URL||'http://localhost:8000';
export async function api(path,options={}){const response=await fetch(base+path,{...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});if(!response.ok)throw new Error('request_failed');return response.json()}
