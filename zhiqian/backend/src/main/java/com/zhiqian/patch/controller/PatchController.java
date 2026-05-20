package com.zhiqian.patch.controller;

import com.zhiqian.patch.PatchGeneratorService;
import com.zhiqian.patch.model.*;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/patch")
@RequiredArgsConstructor
public class PatchController {
    private final PatchGeneratorService service;

    @PostMapping("/generate")
    @PreAuthorize("hasAnyAuthority('DEV','ADMIN')")
    public PatchSet generate(@RequestBody EvidencePack pack) {
        return service.generate(pack);
    }
}
