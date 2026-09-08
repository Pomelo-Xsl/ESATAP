async function api(url, options={}) { const response=await fetch(url,{headers:{'Content-Type':'application/json',...(options.headers||{})},...options}); const data=await response.json().catch(()=>({detail:response.statusText})); if(!response.ok) throw new Error(data.detail||'请求失败'); return data; }
function fmtBytes(value){if(value===null||value===undefined)return '—';const units=['B','KiB','MiB','GiB','TiB'];let i=0,n=Number(value);while(n>=1024&&i<4){n/=1024;i++}return `${n.toFixed(i?2:0)} ${units[i]}`}

