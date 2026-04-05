import Link from "next/link";
import cn from "classnames";

interface Props {
    isSelected?: boolean;
    isMobile?: boolean;
    isBanner?: boolean;
    href?: string;
    children: React.ReactNode;
    /* eslint-disable @typescript-eslint/no-explicit-any */
    [rest: string]: any;
}

export default function NavLink({
    isSelected,
    isMobile,
    isBanner,
    href,
    children,
    ...rest
}: Props) {
    const className = cn(
        rest.className,
        "text-white rounded-md px-3 py-2 font-medium",
        {
            "bg-gray-900": isSelected,
            "text-gray-300 hover:bg-gray-700 hover:text-white": !isSelected && !isBanner,
            "block text-base": isMobile,
            "text-sm": !isMobile,
            "text-gray-300": isBanner,
        }
    );

    if (!href) {
        return (
            <span className={`${className} cursor-pointer`} role="button" onClick={rest.onClick}>{children}</span> // className={className}
        );
    }

    return (
        <Link className={className} href={href}>
            {children}
        </Link>
    );
}
