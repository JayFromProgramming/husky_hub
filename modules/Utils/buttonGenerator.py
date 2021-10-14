import pygame.font


class button:

    def __init__(self, font: pygame.font.Font, rect_bounds: tuple, text: str, button_color: list, font_color: tuple):
        self.x, self.y, w, h = rect_bounds
        surf = pygame.Surface((w, h), pygame.HWSURFACE | pygame.ASYNCBLIT)
        rect = pygame.Rect(0, 0, w, h)
        pygame.draw.rect(surf, button_color, rect)
        text_render = font.render(text, True, font_color).convert_alpha()
        surf.blit(text_render, text_render.get_rect(center=rect.center))
        self.surf = surf
        self.rect = pygame.Rect(rect_bounds)

    def blit(self, screen):
        screen.blit(self.surf, (self.x, self.y))
