from tassflow_app import create_app
import jinja2

app = create_app()

with app.app_context():
    template_content = open('tassflow_app/templates/usuario_panel.html','r',encoding='utf-8').read()
    env = jinja2.Environment()
    template = env.from_string(template_content)
    rendered = template.render(tareas=[], progreso=0, session={'rol':'usuario','usuario':'test'})
    print('len', len(rendered))
