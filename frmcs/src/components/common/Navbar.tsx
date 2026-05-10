"use client";

import { usePathname } from 'next/navigation';
// without DisclosureButton, DisclosurePanel ???
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/react';
import { Bars3Icon } from '@heroicons/react/24/outline';
import { NavLink } from "@/components/common";


export default function Navbar() {
    const pathname = usePathname();


    const isSelected = (path: string) => pathname === path ? true : false;


    const guestLinks = (isMobile: boolean) => (
        <>
            <NavLink isSelected={isSelected("/link1")} isMobile={isMobile} href="/link1">link1</NavLink>
            <NavLink isSelected={isSelected("/link2")} isMobile={isMobile} href="/link2">link2</NavLink>
        </>
    );


    return (
        <Disclosure as="nav" className="bg-gray-800">
            <div className="mx-auto max-w-7xl px-2 sm:px-6 lg:px-8">
                <div className="relative flex h-16 items-center justify-between">
                    <div className="absolute inset-y-0 left-0 flex items-center sm:hidden">
                        {/* Mobile menu button
                        <DisclosureButton className="group relative inline-flex items-center justify-center rounded-md p-2 text-gray-400 hover:bg-gray-700 hover:text-white focus:outline-none focus:ring-2 focus:ring-inset focus:ring-white">
                            <span className="absolute -inset-0.5" />
                            <span className="sr-only">Open main menu</span>
                            <Bars3Icon aria-hidden="true" className="block h-6 w-6 group-data-[open]:hidden" />
                        </DisclosureButton> */}
                    </div>
                    <div className="flex flex-1 items-center justify-center sm:items-stretch sm:justify-start">
                        <div className="flex flex-shrink-0 items-center">
                            <NavLink href="/" isBanner>CONTROL PANEL</NavLink>
                        </div>
                        {/* <div className="hidden sm:ml-6 sm:block">
                            <div className="flex space-x-4">
                                {guestLinks(false)}
                            </div>
                        </div> */}
                    </div>
                </div>
            </div>

            {/* <DisclosurePanel className="sm:hidden">
                <div className="space-y-1 px-2 pb-3 pt-2">
                    {guestLinks(true)}
                </div>
            </DisclosurePanel> */}
        </Disclosure>
    );
}
