import { ChevronRight, Home, Monitor, Mouse, Tv } from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem
} from "@/components/ui/sidebar";
import { Link } from "@tanstack/react-router";
import { useEffect, useState, useTransition } from "react";
import { getAppVersion } from "../actions/app";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "./ui/collapsible";
import { SidebarFooter, SidebarHeader, SidebarMenuSub, SidebarMenuSubButton, SidebarMenuSubItem, SidebarRail, useSidebar } from "./ui/sidebar";

// Menu items.
const items = {
    topLevel: [
        {
            title: "Home",
            url: "/",
            icon: Home,
        },
        {
            title: "Current Stream",
            url: "/stream",
            icon: Tv,
        }
    ],
    navMain: [
        {
            title: "Display",
            icon: Monitor,
            items: [
            {
                title: "View",
                url: "/",
            },
            ],
        },
        {
            title: "Peripherals",
            icon: Mouse,
            isActive: true,
            items: [
              {
                  title: "Connected",
                  url: "/peripherals/connected",
              },
              {
                  title: "Events",
                  url: "/peripherals/events",
              },
              {
                  title: "Snapshots",
                  url: "/peripherals/snapshots",
              },
            ],
        },
    ]
}

export function AppSidebar() {
    const [appVersion, setAppVersion] = useState("0.0.0");
    const [, startGetAppVersion] = useTransition();
    const { open } = useSidebar()
  
    useEffect(
      () => startGetAppVersion(() => getAppVersion().then(setAppVersion)),
      [],
    );

  return (
    <Sidebar collapsible="icon" className="pt-[30px]">
    <SidebarHeader />
      <SidebarContent>
    <SidebarGroup>
        <SidebarMenu>
            {
                items.topLevel.map((item) => (
                    <Link to={item.url} key={item.title}>
                                            <SidebarMenuItem>
                      <SidebarMenuButton tooltip={item.title}>
                        {item.icon && <item.icon />}
                        <span>{item.title}</span>
                      </SidebarMenuButton>
                  </SidebarMenuItem>

                </Link>
                ))
            }

        </SidebarMenu>
    </SidebarGroup>
      <SidebarGroup>
      <SidebarGroupLabel>Entities</SidebarGroupLabel>
      <SidebarMenu>
        {items.navMain.map((item) => (
          <Collapsible
            key={item.title}
            asChild
            defaultOpen={item.isActive}
            className="group/collapsible"
          >
            <SidebarMenuItem>
              <CollapsibleTrigger asChild>
                <SidebarMenuButton tooltip={item.title}>
                  {item.icon && <item.icon />}
                  <span>{item.title}</span>
                  <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                </SidebarMenuButton>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <SidebarMenuSub>
                  {item.items?.map((subItem) => (
                    <SidebarMenuSubItem key={subItem.title}>
                      <SidebarMenuSubButton asChild>
                        <Link to={subItem.url}>
                          <span>{subItem.title}</span>
                        </Link>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                  ))}
                </SidebarMenuSub>
              </CollapsibleContent>
            </SidebarMenuItem>
          </Collapsible>
        ))}
      </SidebarMenu>
    </SidebarGroup>
    <SidebarFooter>
            <footer className={`fixed bottom-0 p-1 font-tomorrow text-muted-foreground flex text-[0.7rem] uppercase justify-end transition-all duration-100 ${open ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-6 pointer-events-none"}`}>
                <p>Version: {appVersion}</p>
            </footer>
      </SidebarFooter>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
