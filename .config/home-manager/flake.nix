{
  description = "My Home Manager flake";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    home-manager.url = "github:nix-community/home-manager";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, home-manager, ... }:
    let system = "x86_64-linux";
    in {
      homeConfigurations = {
        itsjustmech = home-manager.lib.homeManagerConfiguration {
          inherit system;
          pkgs = nixpkgs.legacyPackages.${system};
          modules = [ ./home.nix ];
        };
      };
    };
}
