from flask import Flask, render_template, request, redirect, url_for
import database

app = Flask(__name__)

@app.route('/')
def index():
    groups = database.get_all_groups()
    # Organize data: dict of group -> list of members
    data = {}
    for g in groups:
        members = database.get_members_in_group(g['id'])
        data[g] = members
    
    return render_template('index.html', groups_data=data)

@app.route('/api/pay', methods=['POST'])
def pay():
    user_id = int(request.form.get('user_id'))
    amount = float(request.form.get('amount'))
    database.add_funds(user_id, amount)
    return redirect(url_for('index'))

@app.route('/api/advance', methods=['POST'])
def advance():
    group_id = int(request.form.get('group_id'))
    database.process_month_for_group(group_id)
    return redirect(url_for('index'))

@app.route('/api/set_cost', methods=['POST'])
def set_cost():
    group_id = int(request.form.get('group_id'))
    amount = float(request.form.get('amount'))
    database.set_group_cost(group_id, amount)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
