import {invoke, isTauri} from '@tauri-apps/api/core';
export type Demand = {id:number; title:string; front_id:number; contact:string; channel:string; stage:string; priority:string; due:string|null; next_action:string; return_date:string|null; summary:string};
export const stages = {novo:'Novo', qualificacao:'Em qualificação', preparar_proposta:'Preparar proposta', proposta_enviada:'Proposta enviada', acompanhar:'Acompanhar', ganho:'Ganho', perdido:'Perdido'};
export type Connection = {port:number; token:string};
let connection: Connection|null = null;
export function setConnection(value:Connection){connection=value;}
export async function connect(){
  if(isTauri()) { connection=await invoke<Connection>('connection'); return; }
  throw new Error('Abra o aplicativo desktop. A prévia de navegador não se conecta ao banco real.');
}
export async function api<T>(path:string, method='GET', body?:unknown):Promise<T>{
  if(!connection) throw new Error('Backend indisponível.');
  const response=await fetch(`http://127.0.0.1:${connection.port}${path}`, {method, headers:{Authorization:`Bearer ${connection.token}`,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  if(!response.ok) {
    const error=await response.json().catch(()=>null);
    throw new Error(typeof error?.detail==='string'?error.detail:'Verifique os campos e a data de retorno.');
  }
  return response.status===204?undefined as T:response.json();
}
export async function pullModel(model:string, onProgress:(message:string)=>void){
  if(!connection) throw new Error('Backend indisponível.');
  const response=await fetch(`http://127.0.0.1:${connection.port}/ollama/pull`,{method:'POST', headers:{Authorization:`Bearer ${connection.token}`,'Content-Type':'application/json'},body:JSON.stringify({model})});
  if(!response.ok||!response.body) throw new Error('Não foi possível iniciar o download.');
  const reader=response.body.getReader(), decoder=new TextDecoder(); let buffer='';
  while(true){ const {value,done}=await reader.read(); buffer+=decoder.decode(value,{stream:!done}); const lines=buffer.split('\n'); buffer=lines.pop()||''; for(const line of lines){if(!line.trim())continue; const item=JSON.parse(line); if(item.error)throw new Error(item.error); onProgress(item.total?`${item.status} · ${Math.round(item.completed/item.total*100)}%`:item.status);} if(done)break; }
}
