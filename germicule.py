import json
import sys
import math
from argparse import ArgumentParser, FileType
from pprint import pprint
from os.path import splitext

from graphviz import Digraph

# from xml.sax.saxutils import escape as xmlescape

# Solarised
NAME, _ = splitext(__file__)
COLORS = {
    'bg': '#fdf6e3',  # base3
    'bg_cluster': '#eee8d5',  # base2
    'fg': '#586e75',  # base01
    'risk': [
        '#859900',  # green
        '#2aa198',  # cyan
        '#268bd2',  # blue
        '#6c71c4',  # violet
        '#d33682',  # magenta
        '#dc322f',  # red
    ]
}
UNKNOWN_COUNT = 0


def parse_args(argv):
    """Parse arguments from cli, env and config files."""
    argv = sys.argv[1:] if argv is None else argv[:]

    parser = ArgumentParser(
        description="Visualize your contacts and their COVID risk factors",
        fromfile_prefix_chars="@")
    parser.add_argument('--in-file', help="The JSONC input file", type=FileType('r'), required=True)
    parser.add_argument('--name', help="The graph name", default=NAME)
    # parser.add_argument(
    #     '--out-file', '-o',
    #     help="The output file", type=FileType('w'), default=open(f'{NAME}.gv'))
    # parser.add_argument(
    #     '--source-file',
    #     help="The source file (where to dump the gv source for debugging)",
    #     type=FileType('w'), default=sys.stderr)
    parser.add_argument(
        '--engine', '-K',
        help="The graphviz engine to use",
        default='dot'
    )
    parser.add_argument(
        '--format', '-T',
        help="The graphviz format to use",
        default='svg'
    )
    parser.add_argument(
        '--view',
        help="whether to view the graph",
        default=False,
        action='store_true'
    )

    return parser.parse_args(argv)


def label_escape(node):
    global UNKNOWN_COUNT
    unknown = None
    if not node:
        UNKNOWN_COUNT += 1
        unknown = UNKNOWN_COUNT
    elif 'unknown' in node:
        unknown = node.get('unknown', 0)
    if unknown is not None:
        name = f"❓{unknown}"
        label = '❓'
    else:
        if 'link' in node:
            name = node['link']
        else:
            name = node.get('name')

        label = name
        # label = name.encode('ascii', errors='xmlcharrefreplace').decode('ascii')
        # label = repr(name.encode('ascii', errors='xmlcharrefreplace'))
        # print(type(label), label, name)

    return name, label


def build_graph(node, args):
    global UNKNOWN_COUNT
    clusters = {}
    edges = []

    if (not node) or ('name' not in node and 'unknown' not in node):
        return clusters, edges

    node_name, node_label = label_escape(node)
    node_attrs = {
        'name': node_name,
        'label': node_label,
    }

    risk = node.get('risk')
    # if risk is None:
    #     risk = randrange(0, 5)
    if risk is not None:
        node_attrs['fillcolor'] = COLORS['risk'][math.floor(risk)]

    cluster = node.get('cluster')
    clusters[cluster] = clusters.get(cluster, []) + [node_attrs]

    if not node.get('germicule'):
        return clusters, edges
    for member in node['germicule']:
        if not member:
            UNKNOWN_COUNT += 1
            member = {
                'unknown': UNKNOWN_COUNT
            }
        member_name, member_label = label_escape(member)
        try:
            member_clusters, member_edges = build_graph(member, args)
            for cluster, nodes in member_clusters.items():
                clusters[cluster] = clusters.get(cluster, []) + nodes
            edges.extend(member_edges)

            edge_attrs = {
                'tail_name': node_name,
                'head_name': member_name
            }
            if member:
                if 'contact' in member and member['contact'] is not None:
                    edge_attrs['penwidth'] = str(5 / (member['contact'] + 1))
                    if args.engine in ['sfdp', 'fdp']:
                        edge_attrs['K'] = str((member['contact'] + 1))
                if 'description' in member and member['description'] is not None:
                    edge_attrs['edgetooltip'] = member['description']
            edges.append(edge_attrs)
        except KeyError as exc:
            raise UserWarning(
                f"could not parse node {member}. {exc.__class__.__name__} {exc}")
    return clusters, edges


def main(argv=None):
    args = parse_args(argv)

    data = None

    with args.in_file as stream:
        data = json.load(stream)

    # digraph_params = {
    #     'format': args.format,
    #     'engine': args.engine,
    # }
    # dot = Digraph('Germicule', **digraph_params)
    edge_attrs = {
        'color': COLORS['fg'],
        'fontcolor': COLORS['fg'],
        # 'fontsize': '8',
        'fontname': 'Fira Code',
        # 'arrowhead': 'none'
    }
    node_attrs = {
        'fontname': 'Fira Code',
        'style': 'filled',
        # 'shape': 'plaintext',
        'color': COLORS['bg'],
    }
    graph_attrs = {
        'overlap': 'scale',
        'splines': 'true',
        # 'sep': '1',
        'bgcolor': COLORS['bg'],
        'color': COLORS['bg'],
        'label': args.name,
        'fontcolor': COLORS['fg'],
        'fontname': 'Fira Code',
    }
    dot = Digraph(
        args.name, format=args.format, engine=args.engine,
        edge_attr=edge_attrs, node_attr=node_attrs, graph_attr=graph_attrs)

    clusters, edges = build_graph(data, args)

    pprint(clusters)
    pprint(edges)

    for cluster, nodes in clusters.items():
        if not nodes:
            continue
        if not cluster:
            for node_attrs in nodes:
                dot.node(**node_attrs)
            continue
        cluster_attrs = {
            'name': f'cluster_{cluster}',
            'graph_attr': graph_attrs,
            'node_attr': node_attrs,
            'edge_attr': edge_attrs,
        }
        cluster_attrs['graph_attr'].update({
            'label': cluster,
            'bgcolor': COLORS['bg_cluster'],
            'color': COLORS['bg_cluster'],
            'style': 'filled',
        })
        with dot.subgraph(**cluster_attrs) as subdot:
            for node_attrs in nodes:
                subdot.node(**node_attrs)

    for edge in edges:
        dot.edge(**edge)

    # print(dot.source, file=args.source_file)

    # if args.out_file is None:
    #     out_file = open(f'{NAME}.{args.format}', 'w')
    # else:
    #     out_file = args.out_file

    dot.render(format=args.format, view=args.view)


if __name__ == "__main__":
    main()
