import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import React, { useEffect, useState, useTransition } from "react";
import { getAppVersion } from "../actions/app";
import { AppSidebar } from "../components/app-sidebar";
export default function BaseLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [appVersion, setAppVersion] = useState("0.0.0");
  const [, startGetAppVersion] = useTransition();

  useEffect(
    () => startGetAppVersion(() => getAppVersion().then(setAppVersion)),
    [],
  );

  return (
    <SidebarProvider>
      {/* justify-end */}
      <div className="fixed w-screen bg-background text-foreground border border-border h-[30px] z-[15] flex pl-16 justify-end [-webkit-app-region:drag]">
        <div className="ml-auto pr-2 flex items-center space-x-2 [-webkit-app-region:no-drag]">
          <SidebarTrigger/>
        </div>
      </div>
      <AppSidebar />
      <SidebarInset className="mt-[30px]">
        <div className="m-2 h-full">
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}