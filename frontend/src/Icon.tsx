type Props={name:string;size?:number};
const paths:Record<string,React.ReactNode>={
 create:<><rect x="3" y="3" width="18" height="18" rx="5"/><path d="M12 7v10M7 12h10"/></>,
 image:<><rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 5-5 4 4 4-7 5 8"/></>,
 video:<><rect x="3" y="5" width="18" height="14" rx="3"/><path d="m10 9 5 3-5 3Z"/></>,
 speech:<><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8"/></>,
 music:<><path d="M9 18V5l11-2v13M9 8l11-2"/><ellipse cx="6" cy="18" rx="3" ry="2.5"/><ellipse cx="17" cy="16" rx="3" ry="2.5"/></>,
 ambience:<><path d="M3 9h11a3 3 0 1 0-3-3M3 13h15a3 3 0 1 1-3 3M5 17h4"/></>,
 library:<><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
 workflows:<><rect x="9" y="2" width="6" height="6" rx="2"/><rect x="2" y="16" width="6" height="6" rx="2"/><rect x="16" y="16" width="6" height="6" rx="2"/><path d="M12 8v4M5 16v-4h14v4"/></>,
 composer:<><path d="M3 5h18M3 12h18M3 19h18"/><rect x="5" y="3" width="5" height="4" rx="1"/><rect x="13" y="10" width="5" height="4" rx="1"/><rect x="7" y="17" width="5" height="4" rx="1"/></>,
 queue:<><path d="M9 5h12M9 12h12M9 19h12"/><circle cx="4" cy="5" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="19" r="1"/></>,
 assistant:<><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/><path d="m20 2 .5 1.5L22 4l-1.5.5L20 6l-.5-1.5L18 4l1.5-.5Z"/></>,
 settings:<><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/></>,
 download:<><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></>,
 arrow:<><path d="M5 12h14m-5-5 5 5-5 5"/></>,
 refresh:<><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-1l2 6M4 12l2 6a7 7 0 0 0 12-1"/></>,
 folder:<path d="M3 7V5a2 2 0 0 1 2-2h4l3 4h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>,
 search:<><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
 play:<path d="m8 4 13 8-13 8Z"/>,
 plus:<path d="M12 5v14M5 12h14"/>,
};
export function Icon({name,size=20}:Props){return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]||paths.create}</svg>}
